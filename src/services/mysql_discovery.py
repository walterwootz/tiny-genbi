"""
MySQL schema discovery service.
Connects to MySQL database and extracts schema automatically.
"""

import logging
from typing import Dict, List, Any, Optional
import mysql.connector
from mysql.connector import Error

from models import (
    DatabaseSchema, 
    TableSchema, 
    MySQLCredentials,
    MySQLAutoIndexRequest,
    IndexingResult
)
from pipelines.indexing import SchemaIndexer

logger = logging.getLogger(__name__)


# Query to extract schema from MySQL INFORMATION_SCHEMA
SCHEMA_DISCOVERY_QUERY = """
SELECT
  c.TABLE_NAME                           AS table_name,
  t.TABLE_COMMENT                        AS table_comment,
  c.COLUMN_NAME                          AS column_name,
  c.DATA_TYPE                            AS data_type,
  c.COLUMN_TYPE                          AS column_type,
  c.IS_NULLABLE                          AS is_nullable,
  c.COLUMN_DEFAULT                       AS column_default,
  c.EXTRA                                AS extra,
  c.COLUMN_COMMENT                       AS column_comment,
  CASE WHEN kcu.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
FROM INFORMATION_SCHEMA.COLUMNS AS c
JOIN INFORMATION_SCHEMA.TABLES  AS t
  ON  t.TABLE_SCHEMA = c.TABLE_SCHEMA
  AND t.TABLE_NAME   = c.TABLE_NAME
LEFT JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS tc
  ON  tc.TABLE_SCHEMA    = c.TABLE_SCHEMA
  AND tc.TABLE_NAME      = c.TABLE_NAME
  AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS kcu
  ON  kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
  AND kcu.CONSTRAINT_NAME   = tc.CONSTRAINT_NAME
  AND kcu.TABLE_NAME        = tc.TABLE_NAME
  AND kcu.COLUMN_NAME       = c.COLUMN_NAME
WHERE c.TABLE_SCHEMA = DATABASE()
  AND t.TABLE_TYPE = 'BASE TABLE'
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
"""

# Query for views
SCHEMA_DISCOVERY_QUERY_WITH_VIEWS = """
SELECT
  c.TABLE_NAME                           AS table_name,
  t.TABLE_COMMENT                        AS table_comment,
  c.COLUMN_NAME                          AS column_name,
  c.DATA_TYPE                            AS data_type,
  c.COLUMN_TYPE                          AS column_type,
  c.IS_NULLABLE                          AS is_nullable,
  c.COLUMN_DEFAULT                       AS column_default,
  c.EXTRA                                AS extra,
  c.COLUMN_COMMENT                       AS column_comment,
  CASE WHEN kcu.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
FROM INFORMATION_SCHEMA.COLUMNS AS c
JOIN INFORMATION_SCHEMA.TABLES  AS t
  ON  t.TABLE_SCHEMA = c.TABLE_SCHEMA
  AND t.TABLE_NAME   = c.TABLE_NAME
LEFT JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS tc
  ON  tc.TABLE_SCHEMA    = c.TABLE_SCHEMA
  AND tc.TABLE_NAME      = c.TABLE_NAME
  AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS kcu
  ON  kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
  AND kcu.CONSTRAINT_NAME   = tc.CONSTRAINT_NAME
  AND kcu.TABLE_NAME        = tc.TABLE_NAME
  AND kcu.COLUMN_NAME       = c.COLUMN_NAME
WHERE c.TABLE_SCHEMA = DATABASE()
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
"""

# Query to get foreign key relationships
FOREIGN_KEYS_QUERY = """
SELECT
  kcu.TABLE_NAME              AS from_table,
  kcu.COLUMN_NAME             AS from_column,
  kcu.REFERENCED_TABLE_NAME   AS to_table,
  kcu.REFERENCED_COLUMN_NAME  AS to_column,
  kcu.CONSTRAINT_NAME         AS constraint_name
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS kcu
WHERE kcu.TABLE_SCHEMA = DATABASE()
  AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY kcu.TABLE_NAME, kcu.ORDINAL_POSITION
"""


class MySQLSchemaDiscovery:
    """
    Discovers database schema from MySQL using INFORMATION_SCHEMA.
    """
    
    def __init__(self, indexer: SchemaIndexer):
        self.indexer = indexer
    
    def _connect(self, credentials: MySQLCredentials):
        """Create MySQL connection."""
        try:
            connection = mysql.connector.connect(
                host=credentials.host,
                port=credentials.port,
                user=credentials.user,
                password=credentials.password,
                database=credentials.database,
                charset='utf8mb4',
                use_unicode=True
            )
            
            if connection.is_connected():
                logger.info(f"Successfully connected to MySQL database: {credentials.database}")
                return connection
            else:
                raise Error("Failed to connect to MySQL")
                
        except Error as e:
            logger.error(f"Error connecting to MySQL: {e}")
            raise
    
    def _extract_schema(self, credentials: MySQLCredentials, include_views: bool = False) -> DatabaseSchema:
        """Extract schema from MySQL database."""
        connection = None
        
        try:
            connection = self._connect(credentials)
            cursor = connection.cursor(dictionary=True)
            
            # Execute schema discovery query
            query = SCHEMA_DISCOVERY_QUERY_WITH_VIEWS if include_views else SCHEMA_DISCOVERY_QUERY
            cursor.execute(query)
            rows = cursor.fetchall()
            
            logger.info(f"Retrieved {len(rows)} column records from database")
            
            # Group columns by table
            tables_data: Dict[str, Dict[str, Any]] = {}
            
            for row in rows:
                table_name = row['table_name']
                
                if table_name not in tables_data:
                    tables_data[table_name] = {
                        'name': table_name,
                        'description': row['table_comment'] or None,
                        'table_comment': row['table_comment'] or None,
                        'columns': [],
                        'primary_key': []
                    }
                
                # Add column info
                column_info = {
                    'name': row['column_name'],
                    'type': row['column_type'] or row['data_type'],
                    'nullable': row['is_nullable'] == 'YES',
                    'default': row['column_default'],
                    'extra': row['extra'],
                    'comment': row['column_comment']
                }
                
                tables_data[table_name]['columns'].append(column_info)
                
                # Track primary keys
                if row['is_primary_key'] == 1:
                    tables_data[table_name]['primary_key'].append(row['column_name'])
            
            # Extract foreign key relationships
            cursor.execute(FOREIGN_KEYS_QUERY)
            fk_rows = cursor.fetchall()
            
            relationships = []
            for fk in fk_rows:
                relationships.append({
                    'from_table': fk['from_table'],
                    'from_column': fk['from_column'],
                    'to_table': fk['to_table'],
                    'to_column': fk['to_column'],
                    'constraint_name': fk['constraint_name']
                })
            
            logger.info(f"Found {len(relationships)} foreign key relationships")
            
            # Convert to TableSchema objects
            tables = []
            for table_data in tables_data.values():
                # Include column comments in the column data
                enriched_columns = [
                    {
                        'name': col['name'],
                        'type': col['type'],
                        'description': col['comment'] if col['comment'] else ''
                    }
                    for col in table_data['columns']
                ]
                
                # Build description with table comment and column details
                description = table_data['description'] or f"Table: {table_data['name']}"
                
                # Add column information to description for better context
                col_details = []
                for col in table_data['columns']:
                    col_detail = f"  - {col['name']} ({col['type']})"
                    if col['comment']:
                        col_detail += f": {col['comment']}"
                    if not col['nullable']:
                        col_detail += " [NOT NULL]"
                    if col['extra']:
                        col_detail += f" [{col['extra']}]"
                    col_details.append(col_detail)
                
                if col_details:
                    description += "\nColumns:\n" + "\n".join(col_details)
                
                table = TableSchema(
                    name=table_data['name'],
                    columns=enriched_columns,
                    description=description,
                    table_comment=table_data['table_comment'],
                    primary_key=table_data['primary_key'] if table_data['primary_key'] else None
                )
                tables.append(table)
            
            logger.info(f"Processed {len(tables)} tables")
            
            # Create DatabaseSchema
            schema = DatabaseSchema(
                tables=tables,
                relationships=relationships if relationships else None
            )
            
            return schema
            
        except Error as e:
            logger.error(f"Error extracting schema: {e}")
            raise
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
                logger.info("MySQL connection closed")
    
    def discover_tables(self, credentials: MySQLCredentials, include_views: bool = False) -> Dict[str, Any]:
        """
        Discover tables in MySQL database without indexing.
        Returns table information for user selection.
        """
        connection = None
        
        try:
            connection = self._connect(credentials)
            cursor = connection.cursor(dictionary=True)
            
            # Execute schema discovery query
            query = SCHEMA_DISCOVERY_QUERY_WITH_VIEWS if include_views else SCHEMA_DISCOVERY_QUERY
            cursor.execute(query)
            rows = cursor.fetchall()
            
            logger.info(f"Retrieved {len(rows)} column records from database")
            
            # Group columns by table
            tables_data: Dict[str, Dict[str, Any]] = {}
            
            for row in rows:
                table_name = row['table_name']
                
                if table_name not in tables_data:
                    tables_data[table_name] = {
                        'name': table_name,
                        'comment': row['table_comment'] or None,
                        'column_count': 0,
                        'has_primary_key': False
                    }
                
                tables_data[table_name]['column_count'] += 1
                
                # Track primary keys
                if row['is_primary_key'] == 1:
                    tables_data[table_name]['has_primary_key'] = True
            
            # Get database name
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()['DATABASE()']
            
            # Convert to list
            tables = list(tables_data.values())
            
            logger.info(f"Discovered {len(tables)} tables in database {db_name}")
            
            return {
                "database_name": db_name,
                "tables": tables,
                "total_tables": len(tables)
            }
            
        except Error as e:
            logger.error(f"Error discovering tables: {e}")
            raise
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
                logger.info("MySQL connection closed")
    
    async def discover_and_index(self, request: MySQLAutoIndexRequest) -> IndexingResult:
        """
        Discover schema from MySQL and automatically index it.
        If selected_tables is provided, only those tables will be indexed.
        """
        try:
            logger.info(f"Starting auto-discovery for database: {request.database_id}")
            
            # Extract schema from MySQL
            schema = self._extract_schema(request.credentials, request.include_views)
            
            logger.info(f"Discovered {len(schema.tables)} tables")
            
            # Filter tables if selection is provided
            if request.selected_tables:
                logger.info(f"Filtering to {len(request.selected_tables)} selected tables")
                schema.tables = [
                    table for table in schema.tables 
                    if table.name in request.selected_tables
                ]
                logger.info(f"Filtered to {len(schema.tables)} tables")
            
            # Create indexing request
            from models import IndexingRequest
            index_request = IndexingRequest(
                database_id=request.database_id,
                db_schema=schema
            )
            
            # Index the schema
            result = await self.indexer.index_schema(index_request)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in discover_and_index: {str(e)}")
            return IndexingResult(
                database_id=request.database_id,
                status="failed",
                num_tables=0,
                error=str(e)
            )
    
    def test_connection(self, credentials: MySQLCredentials) -> Dict[str, Any]:
        """Test MySQL connection."""
        try:
            connection = self._connect(credentials)
            cursor = connection.cursor()
            
            # Get database info
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'")
            table_count = cursor.fetchone()[0]
            
            cursor.close()
            connection.close()
            
            return {
                "success": True,
                "database": db_name,
                "version": version,
                "table_count": table_count
            }
            
        except Error as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

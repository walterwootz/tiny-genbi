"""
MySQL query execution service.
Executes SQL queries and formats results.
"""

import logging
import time
from typing import List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
import mysql.connector
from mysql.connector import Error

from models import MySQLCredentials, QueryExecutionResult
from services.sql_validator import SQLValidator, SQLValidationError

logger = logging.getLogger(__name__)


class MySQLQueryExecutor:
    """
    Executes SQL queries on MySQL database and formats results.
    """
    
    def __init__(self):
        pass
    
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
                use_unicode=True,
                autocommit=True,  # Enable autocommit for read queries
                buffered=True     # Use buffered connection to avoid unread results
            )
            
            if connection.is_connected():
                return connection
            else:
                raise Error("Failed to connect to MySQL")
                
        except Error as e:
            logger.error(f"Error connecting to MySQL: {e}")
            raise
    
    def _convert_value(self, value: Any) -> Any:
        """Convert MySQL types to JSON-serializable types."""
        if value is None:
            return None
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        else:
            return value
    
    def execute_query(
        self, 
        credentials: MySQLCredentials, 
        sql: str, 
        max_rows: int = 100
    ) -> QueryExecutionResult:
        """
        Execute SQL query and return results.
        
        Args:
            credentials: MySQL connection credentials
            sql: SQL query to execute
            max_rows: Maximum number of rows to return
            
        Returns:
            QueryExecutionResult with data or error
        """
        connection = None
        cursor = None
        start_time = time.time()
        
        try:
            # Validate SQL using SQLValidator
            is_valid, error_message = SQLValidator.validate(sql)
            if not is_valid:
                return QueryExecutionResult(
                    success=False,
                    error=f"Query validation failed: {error_message}"
                )
            
            # Connect to database
            connection = self._connect(credentials)
            cursor = connection.cursor(dictionary=True, buffered=True)  # Use buffered cursor
            
            # Execute query
            cursor.execute(sql)
            
            # Fetch results
            rows = cursor.fetchmany(max_rows)
            
            # Consume any remaining results to prevent "Unread result found" error
            # This is important when fetchmany doesn't fetch all results
            try:
                while cursor.nextset():
                    pass  # Move to next result set if any
                # Also consume any remaining rows in current set
                while cursor.fetchone():
                    pass  # Consume remaining rows
            except Exception:
                pass  # No more rows or result sets
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Convert rows to JSON-serializable format
            converted_rows = []
            for row in rows:
                converted_row = {
                    key: self._convert_value(value)
                    for key, value in row.items()
                }
                converted_rows.append(converted_row)
            
            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            
            logger.info(f"Query executed successfully: {len(converted_rows)} rows in {execution_time:.2f}ms")
            
            return QueryExecutionResult(
                success=True,
                rows=converted_rows,
                row_count=len(converted_rows),
                columns=columns,
                execution_time_ms=round(execution_time, 2)
            )
            
        except Error as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Error executing query: {e}")
            return QueryExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=round(execution_time, 2)
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Unexpected error: {e}")
            return QueryExecutionResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                execution_time_ms=round(execution_time, 2)
            )
        finally:
            if connection and connection.is_connected():
                if cursor:
                    cursor.close()
                connection.close()
    
    def format_table(self, result: QueryExecutionResult, max_width: int = 100) -> str:
        """
        Format query results as ASCII table.
        
        Args:
            result: Query execution result
            max_width: Maximum width for each column
            
        Returns:
            Formatted ASCII table string
        """
        if not result.success or not result.rows:
            return "No results"
        
        columns = result.columns or []
        rows = result.rows or []
        
        # Calculate column widths
        col_widths = {}
        for col in columns:
            col_widths[col] = min(max(len(str(col)), 10), max_width)
        
        for row in rows:
            for col in columns:
                value_len = len(str(row.get(col, '')))
                col_widths[col] = min(max(col_widths[col], value_len), max_width)
        
        # Build table
        lines = []
        
        # Header separator
        separator = "+" + "+".join(["-" * (col_widths[col] + 2) for col in columns]) + "+"
        lines.append(separator)
        
        # Header
        header = "|" + "|".join([f" {col:<{col_widths[col]}} " for col in columns]) + "|"
        lines.append(header)
        lines.append(separator)
        
        # Rows
        for row in rows:
            values = []
            for col in columns:
                value = str(row.get(col, ''))
                if len(value) > max_width:
                    value = value[:max_width-3] + "..."
                values.append(f" {value:<{col_widths[col]}} ")
            
            row_line = "|" + "|".join(values) + "|"
            lines.append(row_line)
        
        # Footer
        lines.append(separator)
        lines.append(f"Total rows: {result.row_count}")
        
        return "\n".join(lines)

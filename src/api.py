"""
FastAPI web service for the GenBI system.
Provides REST API endpoints for schema indexing and SQL generation.
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from models import (
    IndexingRequest, 
    IndexingResult, 
    QueryRequest, 
    SQLResult,
    QueryStatus,
    MySQLCredentials,
    MySQLAutoIndexRequest,
    MySQLDiscoveryResponse,
    AskRequest,
    AskResponse,
    QueryExecutionResult,
    DatabaseListResponse,
    AddInstructionRequest,
    AddSQLPairRequest,
    KnowledgeBaseListResponse
)
from pipelines.indexing import SchemaIndexer
from pipelines.generation import SQLGenerator
from services.mysql_discovery import MySQLSchemaDiscovery
from services.query_executor import MySQLQueryExecutor
from services.credentials_store import credentials_store
from services.knowledge_base import knowledge_base_store
from config import settings

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
indexer: SchemaIndexer = None
generator: SQLGenerator = None
mysql_discovery: MySQLSchemaDiscovery = None
query_executor: MySQLQueryExecutor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global indexer, generator, mysql_discovery, query_executor
    
    # Startup
    logger.info("Initializing GenBI service...")
    indexer = SchemaIndexer()
    generator = SQLGenerator(indexer)
    mysql_discovery = MySQLSchemaDiscovery(indexer)
    query_executor = MySQLQueryExecutor()
    logger.info("GenBI service initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down GenBI service...")


# Create FastAPI app
app = FastAPI(
    title="GenBI API",
    description="Simplified Text-to-SQL Backend",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "GenBI API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "genbi-api"
    }


@app.post("/api/v1/query", response_model=SQLResult)
async def generate_sql(request: QueryRequest):
    """
    Generate SQL from a natural language question.
    
    This endpoint:
    1. Retrieves relevant schema context based on the question
    2. Uses LLM to generate SQL query
    3. Provides an explanation of the generated query
    """
    try:
        logger.info(f"Received query request: {request.query_id}")
        result = await generator.generate_sql(request)
        
        if result.status == QueryStatus.FAILED:
            raise HTTPException(status_code=500, detail=result.error)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in generate_sql endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/databases", response_model=DatabaseListResponse)
async def list_databases():
    """
    List all configured databases.
    
    Returns database information without passwords.
    """
    try:
        databases = credentials_store.list_databases()
        return DatabaseListResponse(databases=databases)
    except Exception as e:
        logger.error(f"Error listing databases: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/databases/{database_id}")
async def delete_database(database_id: str):
    """
    Delete a database configuration and its indexed data.
    
    This will:
    1. Remove credentials from SQLite
    2. Delete the vector store index
    """
    try:
        logger.info(f"Deleting database: {database_id}")
        
        # Check if database exists
        if not credentials_store.database_exists(database_id):
            raise HTTPException(status_code=404, detail=f"Database '{database_id}' not found")
        
        # Delete credentials
        creds_deleted = credentials_store.delete_credentials(database_id)
        if not creds_deleted:
            logger.warning(f"Failed to delete credentials for {database_id}")
        
        # Delete vector store index
        index_deleted = indexer.delete_index(database_id)
        if not index_deleted:
            logger.warning(f"Failed to delete index for {database_id}")
        
        logger.info(f"Successfully deleted database: {database_id}")
        return {
            "success": True,
            "message": f"Database '{database_id}' deleted successfully",
            "credentials_deleted": creds_deleted,
            "index_deleted": index_deleted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting database: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/mysql/discover", response_model=MySQLDiscoveryResponse)
async def discover_mysql_tables(credentials: MySQLCredentials):
    """
    Discover tables in a MySQL database without indexing.
    
    This endpoint:
    1. Connects to the MySQL database
    2. Queries INFORMATION_SCHEMA to get all table names and basic info
    3. Returns the list of tables for user selection
    
    The user can then select which tables to index.
    """
    try:
        logger.info(f"Discovering tables in MySQL database: {credentials.database}")
        result = mysql_discovery.discover_tables(credentials)
        
        from models import TableInfo
        tables = [
            TableInfo(
                name=t['name'],
                comment=t['comment'],
                column_count=t['column_count'],
                has_primary_key=t['has_primary_key']
            )
            for t in result['tables']
        ]
        
        return MySQLDiscoveryResponse(
            database_name=result['database_name'],
            tables=tables,
            total_tables=result['total_tables']
        )
        
    except Exception as e:
        logger.error(f"Error in discover_mysql_tables endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/mysql/auto-index", response_model=IndexingResult)
async def auto_index_mysql(request: MySQLAutoIndexRequest):
    """
    Auto-discover and index a MySQL database schema.
    
    This endpoint:
    1. Connects to the MySQL database
    2. Queries INFORMATION_SCHEMA to extract all tables and columns
    3. Automatically indexes the schema for later querying
    4. Stores credentials securely in SQLite
    
    No need to manually provide schema - it's discovered automatically!
    """
    try:
        logger.info(f"Auto-indexing MySQL database: {request.database_id}")
        result = await mysql_discovery.discover_and_index(request)
        
        if result.status == "failed":
            raise HTTPException(status_code=500, detail=result.error)
        
        # Store credentials and selected tables after successful indexing
        credentials_store.store_credentials(
            database_id=request.database_id,
            host=request.credentials.host,
            port=request.credentials.port,
            user=request.credentials.user,
            password=request.credentials.password,
            database_name=request.credentials.database,
            selected_tables=request.selected_tables
        )
        
        logger.info(f"Successfully auto-indexed {result.num_tables} tables from MySQL and stored credentials")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in auto_index_mysql endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/databases/{database_id}/schema")
async def get_database_schema(database_id: str):
    """
    Get complete database schema with tables, columns, comments, and relationships.
    Only returns tables that were selected during indexing.
    
    Returns:
    - Tables with columns and their comments
    - Foreign key relationships
    - Primary keys
    """
    try:
        logger.info(f"Fetching schema for database: {database_id}")
        
        # Retrieve credentials and selected tables
        credentials_dict = credentials_store.get_credentials(database_id)
        if not credentials_dict:
            raise HTTPException(
                status_code=404,
                detail=f"Database '{database_id}' not found"
            )
        
        # Convert to MySQLCredentials
        credentials = MySQLCredentials(
            host=credentials_dict['host'],
            port=credentials_dict['port'],
            user=credentials_dict['user'],
            password=credentials_dict['password'],
            database=credentials_dict['database']
        )
        
        # Get selected tables (tables that were indexed)
        selected_tables = credentials_dict.get('selected_tables')
        
        # Get schema from mysql_discovery
        schema = mysql_discovery._extract_schema(credentials, include_views=False)
        
        # Filter tables to only show indexed ones
        if selected_tables:
            filtered_tables = [table for table in schema.tables if table.name in selected_tables]
            logger.info(f"Filtered to {len(filtered_tables)} indexed tables out of {len(schema.tables)} total")
        else:
            # If no selected_tables info, show all (backward compatibility)
            filtered_tables = schema.tables
            logger.info(f"No selected_tables info found, showing all {len(filtered_tables)} tables")
        
        # Filter relationships to only include those between indexed tables
        filtered_relationships = []
        if schema.relationships and selected_tables:
            for rel in schema.relationships:
                if rel["from_table"] in selected_tables and rel["to_table"] in selected_tables:
                    filtered_relationships.append(rel)
        elif schema.relationships:
            filtered_relationships = schema.relationships
        
        # Format response
        response = {
            "database_id": database_id,
            "database_name": credentials.database,
            "tables": [
                {
                    "name": table.name,
                    "description": table.table_comment or "",  # Use only table_comment, not the full description
                    "columns": [
                        {
                            "name": col["name"],
                            "type": col["type"],
                            "description": col.get("description", "")
                        }
                        for col in table.columns
                    ],
                    "primary_key": table.primary_key
                }
                for table in filtered_tables
            ],
            "relationships": [
                {
                    "from_table": rel["from_table"],
                    "from_column": rel["from_column"],
                    "to_table": rel["to_table"],
                    "to_column": rel["to_column"],
                    "constraint_name": rel["constraint_name"]
                }
                for rel in filtered_relationships
            ]
        }
        
        logger.info(f"Retrieved schema with {len(filtered_tables)} indexed tables and {len(filtered_relationships)} relationships")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching database schema: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/databases/{database_id}/reindex", response_model=IndexingResult)
async def reindex_database(database_id: str):
    """
    Re-index an existing database.
    
    This endpoint:
    1. Retrieves stored credentials and selected tables
    2. Deletes the old index
    3. Re-discovers and re-indexes the same tables
    """
    try:
        logger.info(f"Re-indexing database: {database_id}")
        
        # Retrieve credentials and selected tables
        credentials_dict = credentials_store.get_credentials(database_id)
        if not credentials_dict:
            raise HTTPException(
                status_code=404,
                detail=f"Database '{database_id}' not found"
            )
        
        # Convert to MySQLCredentials
        credentials = MySQLCredentials(
            host=credentials_dict['host'],
            port=credentials_dict['port'],
            user=credentials_dict['user'],
            password=credentials_dict['password'],
            database=credentials_dict['database']
        )
        
        selected_tables = credentials_dict.get('selected_tables')
        
        logger.info(f"Found credentials for {database_id}, selected tables: {selected_tables}")
        
        # Delete old index
        indexer.delete_index(database_id)
        logger.info(f"Deleted old index for {database_id}")
        
        # Create re-index request
        reindex_request = MySQLAutoIndexRequest(
            database_id=database_id,
            credentials=credentials,
            selected_tables=selected_tables,
            include_views=False
        )
        
        # Re-index
        result = await mysql_discovery.discover_and_index(reindex_request)
        
        if result.status == "failed":
            raise HTTPException(status_code=500, detail=result.error)
        
        logger.info(f"Successfully re-indexed {result.num_tables} tables for {database_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error re-indexing database: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """
    Ask a question in natural language and get complete answer with results.
    
    This endpoint performs the complete workflow:
    1. Retrieves stored credentials for the database
    2. Generates SQL from natural language question
    3. Executes the SQL query on MySQL database
    4. Formats results as a table
    5. Generates natural language explanation of the results
    
    Returns everything in one response!
    """
    try:
        logger.info(f"Processing ask request for database: {request.database_id}")
        
        # Step 1: Retrieve credentials from store
        credentials_dict = credentials_store.get_credentials(request.database_id)
        if not credentials_dict:
            raise HTTPException(
                status_code=404,
                detail=f"Database '{request.database_id}' not found. Please index it first using /api/v1/mysql/auto-index"
            )
        
        # Convert dict to MySQLCredentials object
        credentials = MySQLCredentials(
            host=credentials_dict['host'],
            port=credentials_dict['port'],
            user=credentials_dict['user'],
            password=credentials_dict['password'],
            database=credentials_dict['database']
        )
        
        # Step 2: Generate SQL
        from models import QueryRequest
        query_request = QueryRequest(
            question=request.question,
            database_id=request.database_id
        )
        
        sql_result = await generator.generate_sql(query_request)
        
        if sql_result.status == QueryStatus.FAILED:
            raise HTTPException(
                status_code=500, 
                detail=f"SQL generation failed: {sql_result.error}"
            )
        
        logger.info(f"Generated SQL: {sql_result.sql}")
        
        # Step 3: Execute SQL query with auto-fix on error (max 5 attempts)
        max_fix_attempts = 5
        current_sql = sql_result.sql
        execution_result = None
        previous_attempts = []
        
        for attempt in range(1, max_fix_attempts + 1):
            logger.info(f"Executing SQL (attempt {attempt}/{max_fix_attempts})")
            
            execution_result = query_executor.execute_query(
                credentials=credentials,
                sql=current_sql or "",
                max_rows=request.max_rows
            )
            
            # Success! Break the loop
            if execution_result.success:
                if attempt > 1:
                    logger.info(f"✅ SQL fixed successfully after {attempt} attempts")
                    # Update the sql_result with the fixed SQL
                    sql_result.sql = current_sql
                break
            
            # Error occurred
            logger.warning(f"❌ Attempt {attempt} failed: {execution_result.error}")
            
            # If this was the last attempt, stop trying
            if attempt >= max_fix_attempts:
                logger.error(f"Max fix attempts ({max_fix_attempts}) reached. Giving up.")
                break
            
            # Record this failed attempt
            previous_attempts.append({
                "sql": current_sql or "",
                "error": execution_result.error or "Unknown error"
            })
            
            # Try to fix the SQL
            logger.info(f"🔧 Attempting to fix SQL (attempt {attempt + 1}/{max_fix_attempts})...")
            
            try:
                # Get schema context for fixing
                schema_docs = generator.indexer.retrieve_context(
                    request.database_id,
                    request.question,
                    k=10
                )
                schema_context = generator._format_schema_context(schema_docs)
                
                # Generate fixed SQL
                fixed_sql = await generator.fix_sql(
                    question=request.question,
                    failed_sql=current_sql or "",
                    error_message=execution_result.error or "Unknown error",
                    schema_context=schema_context,
                    reasoning=sql_result.reasoning or "",
                    attempt_number=attempt + 1,
                    previous_attempts=previous_attempts
                )
                
                current_sql = fixed_sql
                logger.info(f"Generated fix: {current_sql[:100]}...")
                
            except Exception as fix_error:
                logger.error(f"Error generating fix: {str(fix_error)}")
                break
        
        # Type assertion for type checker
        assert execution_result is not None, "execution_result should be set by now"
        
        # Check final result
        if not execution_result.success:
            logger.error(f"Query execution failed after {len(previous_attempts) + 1} attempts")
            error_details = f"Query execution failed after {len(previous_attempts) + 1} attempts.\n\nFinal error: {execution_result.error}"
            
            if previous_attempts:
                error_details += f"\n\nAttempted {len(previous_attempts)} fixes, all failed."
            
            # Return partial response with error details
            return AskResponse(
                query_id=sql_result.query_id,
                question=request.question,
                sql=current_sql or "",
                sql_explanation=sql_result.explanation or "",
                reasoning=sql_result.reasoning,
                execution_result=execution_result,
                natural_language_answer=error_details,
                metadata={
                    "model": settings.llm_model,
                    "max_rows": request.max_rows,
                    "fix_attempts": len(previous_attempts) + 1,
                    "auto_fixed": False
                }
            )
        
        logger.info(f"Query executed: {execution_result.row_count} rows returned")
        
        # If query was auto-fixed, regenerate explanation for the fixed SQL
        was_auto_fixed = len(previous_attempts) > 0
        if was_auto_fixed:
            logger.info("Query was auto-fixed, regenerating explanation for corrected SQL...")
            sql_result.explanation = await generator.explanation_chain.ainvoke({
                "question": request.question,
                "sql": current_sql
            })
            sql_result.explanation = sql_result.explanation.strip()
        
        # Step 4: Format results as table
        formatted_table = query_executor.format_table(execution_result)
        
        # Step 5: Generate natural language answer
        natural_language_answer = await generator.analyze_results(
            question=request.question,
            sql=sql_result.sql or current_sql or "",
            results=execution_result.rows or [],
            row_count=execution_result.row_count
        )
        
        logger.info("Generated natural language answer")
        
        # Return complete response
        return AskResponse(
            query_id=sql_result.query_id,
            question=request.question,
            sql=current_sql or sql_result.sql or "",
            sql_explanation=sql_result.explanation or "",
            reasoning=sql_result.reasoning,
            execution_result=execution_result,
            natural_language_answer=natural_language_answer,
            formatted_table=formatted_table,
            metadata={
                "model": settings.llm_model,
                "max_rows": request.max_rows,
                "execution_time_ms": execution_result.execution_time_ms,
                "fix_attempts": len(previous_attempts) + 1,
                "auto_fixed": was_auto_fixed
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ask_question endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ask/stream")
async def ask_question_stream(request: AskRequest):
    """
    Ask a question with real-time streaming of the reasoning process.
    
    Returns Server-Sent Events (SSE) stream with progress updates:
    - event: reasoning_start
    - event: reasoning_chunk (streaming reasoning text)
    - event: reasoning_complete
    - event: sql_generated
    - event: sql_executing
    - event: sql_success / sql_error
    - event: complete (final answer)
    """
    
    async def event_generator():
        try:
            # Send event helper
            def send_event(event_type: str, data: dict):
                return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
            
            logger.info(f"Starting streaming ask for database: {request.database_id}")
            
            # Step 1: Retrieve credentials
            yield send_event("status", {"step": "credentials", "message": "Retrieving database credentials..."})
            
            credentials_dict = credentials_store.get_credentials(request.database_id)
            if not credentials_dict:
                yield send_event("error", {"message": f"Database '{request.database_id}' not found"})
                return
            
            credentials = MySQLCredentials(
                host=credentials_dict['host'],
                port=credentials_dict['port'],
                user=credentials_dict['user'],
                password=credentials_dict['password'],
                database=credentials_dict['database']
            )
            
            # Step 2: Retrieve schema context
            yield send_event("status", {"step": "schema", "message": "Retrieving relevant schema..."})
            
            from models import QueryRequest
            query_request = QueryRequest(
                question=request.question,
                database_id=request.database_id
            )
            
            schema_docs = generator.indexer.retrieve_context(
                request.database_id,
                request.question,
                k=10
            )
            
            if not schema_docs:
                yield send_event("error", {"message": "No schema found"})
                return
            
            schema_context = generator._format_schema_context(schema_docs)
            
            # Step 3: Generate reasoning (stream it!)
            yield send_event("reasoning_start", {"message": "Analyzing your question..."})
            
            reasoning_chunks = []
            async for chunk in generator.reasoning_chain.astream({
                "schema_context": schema_context,
                "question": request.question
            }):
                reasoning_chunks.append(chunk)
                yield send_event("reasoning_chunk", {"chunk": chunk})
            
            reasoning = "".join(reasoning_chunks).strip()
            yield send_event("reasoning_complete", {"reasoning": reasoning})
            
            # Step 4: Generate SQL
            yield send_event("status", {"step": "sql_generation", "message": "Generating SQL query..."})
            
            sql = await generator.sql_chain.ainvoke({
                "schema_context": schema_context,
                "question": request.question,
                "reasoning": reasoning
            })
            
            sql = generator._clean_sql(sql)
            yield send_event("sql_generated", {"sql": sql})
            
            # Step 5: Execute SQL with auto-fix on error (max 5 attempts)
            yield send_event("status", {"step": "sql_execution", "message": "Executing query..."})
            
            max_fix_attempts = 5
            current_sql = sql
            execution_result = None
            previous_attempts = []
            
            for attempt in range(1, max_fix_attempts + 1):
                logger.info(f"Executing SQL (attempt {attempt}/{max_fix_attempts})")
                
                execution_result = query_executor.execute_query(
                    credentials=credentials,
                    sql=current_sql,
                    max_rows=request.max_rows
                )
                
                # Success! Break the loop
                if execution_result.success:
                    if attempt > 1:
                        logger.info(f"✅ SQL fixed successfully after {attempt} attempts")
                        # Update the SQL
                        sql = current_sql
                        yield send_event("sql_fixed", {
                            "sql": sql,
                            "attempts": attempt
                        })
                    break
                
                # Error occurred
                logger.warning(f"❌ Attempt {attempt} failed: {execution_result.error}")
                
                # If this was the last attempt, stop trying
                if attempt >= max_fix_attempts:
                    logger.error(f"Max fix attempts ({max_fix_attempts}) reached. Giving up.")
                    yield send_event("sql_error", {
                        "error": f"Query execution failed after {max_fix_attempts} attempts.\n\nFinal error: {execution_result.error}",
                        "sql": current_sql,
                        "attempts": attempt
                    })
                    return
                
                # Record this failed attempt
                previous_attempts.append({
                    "sql": current_sql,
                    "error": execution_result.error or "Unknown error"
                })
                
                # Try to fix the SQL
                logger.info(f"🔧 Attempting to fix SQL (attempt {attempt + 1}/{max_fix_attempts})...")
                yield send_event("status", {
                    "step": "sql_fixing",
                    "message": f"Fixing SQL query (attempt {attempt + 1}/{max_fix_attempts})..."
                })
                
                try:
                    # Generate fixed SQL
                    fixed_sql = await generator.fix_sql(
                        question=request.question,
                        failed_sql=current_sql,
                        error_message=execution_result.error or "Unknown error",
                        schema_context=schema_context,
                        reasoning=reasoning,
                        attempt_number=attempt + 1,
                        previous_attempts=previous_attempts
                    )
                    
                    current_sql = fixed_sql
                    logger.info(f"Generated fix: {current_sql[:100]}...")
                    
                except Exception as fix_error:
                    logger.error(f"Error generating fix: {str(fix_error)}")
                    yield send_event("sql_error", {
                        "error": f"Error generating fix: {str(fix_error)}",
                        "sql": current_sql
                    })
                    return
            
            # Type assertion for type checker
            assert execution_result is not None, "execution_result should be set by now"
            
            if not execution_result.success:
                # Already sent error event above
                return
            
            yield send_event("sql_success", {
                "row_count": execution_result.row_count,
                "execution_time_ms": execution_result.execution_time_ms,
                "auto_fixed": len(previous_attempts) > 0,
                "fix_attempts": len(previous_attempts) + 1
            })
            
            # If query was auto-fixed, regenerate explanation for the fixed SQL
            was_auto_fixed = len(previous_attempts) > 0
            if was_auto_fixed:
                logger.info("Query was auto-fixed, regenerating explanation for corrected SQL...")
            
            # Step 6: Generate explanation
            yield send_event("status", {"step": "explanation", "message": "Generating explanation..."})
            
            explanation = await generator.explanation_chain.ainvoke({
                "question": request.question,
                "sql": sql
            })
            
            yield send_event("explanation_complete", {
                "explanation": explanation.strip()
            })
            
            # Step 7: Generate natural language answer
            yield send_event("status", {"step": "answer", "message": "Analyzing results..."})
            
            natural_language_answer = await generator.analyze_results(
                question=request.question,
                sql=sql,
                results=execution_result.rows or [],
                row_count=execution_result.row_count
            )
            
            formatted_table = query_executor.format_table(execution_result)
            
            yield send_event("answer_complete", {
                "natural_language_answer": natural_language_answer
            })
            
            # Step 8: Send complete result
            yield send_event("complete", {
                "query_id": query_request.query_id,
                "question": request.question,
                "sql": sql,
                "sql_explanation": explanation.strip(),
                "reasoning": reasoning,
                "execution_result": {
                    "success": execution_result.success,
                    "row_count": execution_result.row_count,
                    "execution_time_ms": execution_result.execution_time_ms,
                    "rows": execution_result.rows,
                    "columns": execution_result.columns
                },
                "natural_language_answer": natural_language_answer,
                "formatted_table": formatted_table,
                "metadata": {
                    "model": settings.llm_model,
                    "max_rows": request.max_rows,
                    "num_schema_docs": len(schema_docs),
                    "fix_attempts": len(previous_attempts) + 1,
                    "auto_fixed": was_auto_fixed
                }
            })
            
        except Exception as e:
            logger.error(f"Error in streaming ask: {str(e)}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# Knowledge Base Endpoints

@app.get("/api/v1/databases/{database_id}/knowledge-base", response_model=KnowledgeBaseListResponse)
async def get_knowledge_base(database_id: str):
    """
    Get all knowledge base entries for a database.
    
    Returns both instructions and SQL pairs.
    """
    try:
        instructions = knowledge_base_store.get_instructions(database_id)
        sql_pairs = knowledge_base_store.get_sql_pairs(database_id)
        
        return KnowledgeBaseListResponse(
            instructions=instructions,
            sql_pairs=sql_pairs,
            total_count=len(instructions) + len(sql_pairs)
        )
        
    except Exception as e:
        logger.error(f"Error getting knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/databases/{database_id}/knowledge-base/instructions")
async def add_instruction(database_id: str, request: AddInstructionRequest):
    """
    Add a new instruction to the knowledge base.
    
    The instruction will be indexed and available for future queries.
    """
    try:
        logger.info(f"Adding instruction to knowledge base for {database_id}")
        
        # Add to database
        instruction = knowledge_base_store.add_instruction(
            database_id=database_id,
            title=request.title,
            content=request.content
        )
        
        # Index in vector store
        success = indexer.index_knowledge_base_instruction(
            database_id=database_id,
            instruction_id=instruction.id,
            title=instruction.title,
            content=instruction.content
        )
        
        if not success:
            logger.warning(f"Failed to index instruction in vector store")
        
        logger.info(f"Added instruction {instruction.id}")
        return instruction
        
    except Exception as e:
        logger.error(f"Error adding instruction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/databases/{database_id}/knowledge-base/sql-pairs")
async def add_sql_pair(database_id: str, request: AddSQLPairRequest):
    """
    Add a new SQL pair to the knowledge base.
    
    The SQL pair will be indexed and available as an example for future queries.
    """
    try:
        logger.info(f"Adding SQL pair to knowledge base for {database_id}")
        
        # Add to database
        sql_pair = knowledge_base_store.add_sql_pair(
            database_id=database_id,
            question=request.question,
            sql=request.sql,
            description=request.description
        )
        
        # Index in vector store
        success = indexer.index_knowledge_base_sql_pair(
            database_id=database_id,
            pair_id=sql_pair.id,
            question=sql_pair.question,
            sql=sql_pair.sql,
            description=sql_pair.description
        )
        
        if not success:
            logger.warning(f"Failed to index SQL pair in vector store")
        
        logger.info(f"Added SQL pair {sql_pair.id}")
        return sql_pair
        
    except Exception as e:
        logger.error(f"Error adding SQL pair: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/knowledge-base/instructions/{instruction_id}")
async def delete_instruction(instruction_id: str):
    """Delete an instruction from the knowledge base."""
    try:
        success = knowledge_base_store.delete_instruction(instruction_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Instruction not found")
        
        # Note: We don't remove from vector store as FAISS doesn't support deletion easily
        # The instruction will just not match anymore since it's not in DB
        
        return {"success": True, "message": "Instruction deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting instruction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/knowledge-base/sql-pairs/{pair_id}")
async def delete_sql_pair(pair_id: str):
    """Delete a SQL pair from the knowledge base."""
    try:
        success = knowledge_base_store.delete_sql_pair(pair_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="SQL pair not found")
        
        # Note: We don't remove from vector store as FAISS doesn't support deletion easily
        # The pair will just not match anymore since it's not in DB
        
        return {"success": True, "message": "SQL pair deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting SQL pair: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )

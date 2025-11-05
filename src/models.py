"""
Core domain models for the simplified GenBI system.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TableSchema(BaseModel):
    """Represents a database table schema."""
    name: str
    columns: List[Dict[str, str]]  # [{"name": "col1", "type": "int"}, ...]
    description: Optional[str] = None
    table_comment: Optional[str] = None  # Original table comment from database
    primary_key: Optional[List[str]] = None
    
    
class DatabaseSchema(BaseModel):
    """Represents the entire database schema."""
    tables: List[TableSchema]
    relationships: Optional[List[Dict[str, Any]]] = None  # foreign key relationships
    

class QueryStatus(str, Enum):
    """Status of a query request."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    

class QueryRequest(BaseModel):
    """Request to convert natural language to SQL."""
    query_id: str = Field(default_factory=lambda: f"q_{datetime.now().timestamp()}")
    question: str = Field(..., description="Natural language question")
    database_id: str = Field(..., description="ID of the database schema to query")
    

class SQLResult(BaseModel):
    """Result of SQL generation."""
    query_id: str
    status: QueryStatus
    sql: Optional[str] = None
    explanation: Optional[str] = None
    reasoning: Optional[str] = None  # Step-by-step reasoning/plan
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    

class IndexingRequest(BaseModel):
    """Request to index a database schema."""
    database_id: str
    db_schema: DatabaseSchema
    

class IndexingResult(BaseModel):
    """Result of schema indexing."""
    database_id: str
    status: str
    indexed_at: datetime = Field(default_factory=datetime.now)
    num_tables: int
    error: Optional[str] = None


class MySQLCredentials(BaseModel):
    """MySQL database connection credentials."""
    host: str = Field(..., description="MySQL host (e.g., localhost)")
    port: int = Field(3306, description="MySQL port")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    database: str = Field(..., description="Database name")
    

class MySQLAutoIndexRequest(BaseModel):
    """Request to auto-discover and index a MySQL database."""
    database_id: str = Field(..., description="Unique ID for this database")
    credentials: MySQLCredentials
    include_views: bool = Field(False, description="Include database views in schema")
    selected_tables: Optional[List[str]] = Field(None, description="List of table names to index (None = all tables)")


class TableInfo(BaseModel):
    """Information about a database table."""
    name: str = Field(..., description="Table name")
    comment: Optional[str] = Field(None, description="Table comment/description")
    column_count: int = Field(..., description="Number of columns")
    has_primary_key: bool = Field(..., description="Whether table has primary key")


class MySQLDiscoveryResponse(BaseModel):
    """Response from MySQL discovery endpoint."""
    database_name: str
    tables: List[TableInfo]
    total_tables: int


class QueryExecutionResult(BaseModel):
    """Result of executing a SQL query."""
    success: bool
    rows: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    columns: Optional[List[str]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class AskRequest(BaseModel):
    """Request to ask a question and get results (SQL generation + execution)."""
    question: str = Field(..., description="Natural language question")
    database_id: str = Field(..., description="ID of the indexed database")
    max_rows: int = Field(100, description="Maximum rows to return")


class AskResponse(BaseModel):
    """Complete response with SQL, execution results, and natural language explanation."""
    query_id: str
    question: str
    sql: str
    sql_explanation: str
    reasoning: Optional[str] = None  # Step-by-step reasoning/plan
    execution_result: QueryExecutionResult
    natural_language_answer: Optional[str] = None
    formatted_table: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DatabaseInfo(BaseModel):
    """Database information (without sensitive credentials)."""
    database_id: str
    host: str
    port: int
    user: str
    database_name: str
    created_at: str


class DatabaseListResponse(BaseModel):
    """Response for listing databases."""
    databases: List[DatabaseInfo]


# Knowledge Base Models

class KnowledgeBaseType(str, Enum):
    """Type of knowledge base entry."""
    INSTRUCTION = "instruction"
    SQL_PAIR = "sql_pair"


class KnowledgeBaseInstruction(BaseModel):
    """Generic instruction/information about the database."""
    id: Optional[str] = Field(None, description="Unique ID (auto-generated)")
    database_id: str = Field(..., description="Database this instruction applies to")
    title: str = Field(..., description="Short title/summary")
    content: str = Field(..., description="Instruction text (e.g., info about tables, possible values, business rules)")
    created_at: datetime = Field(default_factory=datetime.now)


class KnowledgeBaseSQLPair(BaseModel):
    """Question-SQL pair example."""
    id: Optional[str] = Field(None, description="Unique ID (auto-generated)")
    database_id: str = Field(..., description="Database this pair applies to")
    question: str = Field(..., description="Natural language question")
    sql: str = Field(..., description="Corresponding SQL query")
    description: Optional[str] = Field(None, description="Optional explanation")
    created_at: datetime = Field(default_factory=datetime.now)


class AddInstructionRequest(BaseModel):
    """Request to add a knowledge base instruction."""
    database_id: str
    title: str
    content: str


class AddSQLPairRequest(BaseModel):
    """Request to add a SQL pair."""
    database_id: str
    question: str
    sql: str
    description: Optional[str] = None


class KnowledgeBaseListResponse(BaseModel):
    """Response listing knowledge base entries."""
    instructions: List[KnowledgeBaseInstruction]
    sql_pairs: List[KnowledgeBaseSQLPair]
    total_count: int


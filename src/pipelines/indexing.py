"""
Schema indexing pipeline - stores database schemas for retrieval.
"""

import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from models import DatabaseSchema, TableSchema, IndexingRequest, IndexingResult
from config import settings

logger = logging.getLogger(__name__)


def clean_text(text: str, max_length: int = 1000) -> str:
    """Clean text to remove invalid tokens and limit length."""
    if not text:
        return ""
    
    # Convert to string and strip
    text = str(text).strip()
    
    # Remove control characters and non-printable characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Keep only ASCII printable characters (space to tilde)
    # This removes accented characters and special Unicode that might cause issues
    text = ''.join(char if 32 <= ord(char) <= 126 else ' ' for char in text)
    
    # Replace multiple whitespaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()


class SchemaIndexer:
    """
    Indexes database schemas into a vector store for semantic retrieval.
    """
    
    def __init__(self):
        # Initialize embeddings with optional base_url for local models
        embedding_kwargs = {
            "model": settings.embedding_model,
        }
        
        # Add API key if provided (optional for local models)
        if settings.embedding_api_key:
            embedding_kwargs["openai_api_key"] = settings.embedding_api_key
        
        # Add base_url for local embeddings (e.g., Ollama, LocalAI)
        if settings.embedding_base_url:
            embedding_kwargs["openai_api_base"] = settings.embedding_base_url
            logger.info(f"Using custom embedding endpoint: {settings.embedding_base_url}")
        
        self.embeddings = OpenAIEmbeddings(**embedding_kwargs)
        self.vector_store_path = Path(settings.vector_store_path)
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        
        # Create directory for indexed content dumps (human-readable)
        self.dumps_path = Path("./data/indexed_dumps")
        self.dumps_path.mkdir(parents=True, exist_ok=True)
        
        self.stores: Dict[str, FAISS] = {}
        
    def _schema_to_documents(self, schema: DatabaseSchema, database_id: str) -> List[Document]:
        """Convert database schema to documents for indexing."""
        documents = []
        
        for table in schema.tables:
            # Create document for each table
            table_text = self._format_table_info(table)
            
            metadata = {
                "database_id": database_id,
                "table_name": table.name,
                "type": "table",
                "columns": [col["name"] for col in table.columns]
            }
            
            doc = Document(
                page_content=table_text,
                metadata=metadata
            )
            documents.append(doc)
            
            # Create documents for each column with rich context
            for col in table.columns:
                col_text = self._format_column_info(table, col)
                col_metadata = {
                    "database_id": database_id,
                    "table_name": table.name,
                    "column_name": col["name"],
                    "column_type": col["type"],
                    "type": "column"
                }
                col_doc = Document(
                    page_content=col_text,
                    metadata=col_metadata
                )
                documents.append(col_doc)
        
        # Index relationships (foreign keys) for better JOIN generation
        if schema.relationships:
            relationships_text = self._format_relationships_info(schema.relationships)
            rel_doc = Document(
                page_content=relationships_text,
                metadata={
                    "database_id": database_id,
                    "type": "relationships"
                }
            )
            documents.append(rel_doc)
                
        return documents
    
    def _format_table_info(self, table: TableSchema) -> str:
        """Format table information as text."""
        # Clean and sanitize text to avoid invalid tokens
        table_name = clean_text(table.name, max_length=200)
        description = clean_text(table.description, max_length=500) if table.description else ""
        
        text = f"Table: {table_name}\n"
        if description:
            text += f"Description: {description}\n"
        text += "Columns:\n"
        for col in table.columns:
            col_name = clean_text(col['name'], max_length=200)
            col_type = clean_text(col['type'], max_length=100)
            text += f"  - {col_name} ({col_type})"
            
            # Add column description/comment if available
            if 'description' in col and col['description']:
                col_desc = clean_text(col['description'], max_length=300)
                text += f": {col_desc}"
            
            text += "\n"
            
        if table.primary_key:
            pk_list = [clean_text(pk, max_length=200) for pk in table.primary_key]
            text += f"Primary Key: {', '.join(pk_list)}\n"
        return text
    
    def _format_column_info(self, table: TableSchema, column: Dict[str, str]) -> str:
        """Format column information with table context."""
        # Clean and sanitize text
        col_name = clean_text(column['name'], max_length=200)
        table_name = clean_text(table.name, max_length=200)
        col_type = clean_text(column['type'], max_length=100)
        
        text = f"Column: {col_name}\n"
        text += f"Table: {table_name}\n"
        text += f"Type: {col_type}\n"
        
        # Add column description/comment if available
        if 'description' in column and column['description']:
            col_desc = clean_text(column['description'], max_length=500)
            text += f"Column Description: {col_desc}\n"
        
        if table.description:
            description = clean_text(table.description, max_length=500)
            text += f"Table Description: {description}\n"
        return text
    
    def _format_relationships_info(self, relationships: List[Dict[str, Any]]) -> str:
        """Format foreign key relationships for indexing."""
        text = "DATABASE RELATIONSHIPS (Foreign Keys):\n\n"
        text += "Use these relationships to JOIN tables correctly:\n\n"
        
        for rel in relationships:
            from_table = clean_text(rel['from_table'], max_length=200)
            from_col = clean_text(rel['from_column'], max_length=200)
            to_table = clean_text(rel['to_table'], max_length=200)
            to_col = clean_text(rel['to_column'], max_length=200)
            
            text += f"- {from_table}.{from_col} → {to_table}.{to_col}\n"
            text += f"  JOIN {to_table} ON {from_table}.{from_col} = {to_table}.{to_col}\n\n"
        
        return text
    
    def _save_indexed_content_dump(
        self, 
        database_id: str, 
        documents: List[Document],
        schema: DatabaseSchema
    ) -> None:
        """
        Save indexed content to a human-readable JSON file.
        This allows inspection of what was actually indexed into the vector store.
        """
        try:
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{database_id}_{timestamp}.json"
            filepath = self.dumps_path / filename
            
            # Prepare data structure
            indexed_data = {
                "database_id": database_id,
                "indexed_at": datetime.now().isoformat(),
                "total_documents": len(documents),
                "total_tables": len(schema.tables),
                "embedding_model": settings.embedding_model,
                "tables_summary": [],
                "indexed_documents": []
            }
            
            # Add table summaries
            for table in schema.tables:
                table_info = {
                    "table_name": table.name,
                    "description": table.description,
                    "total_columns": len(table.columns),
                    "primary_key": table.primary_key,
                    "columns": []
                }
                
                for col in table.columns:
                    col_data = col if isinstance(col, dict) else {
                        "name": getattr(col, 'name', str(col)),
                        "type": getattr(col, 'type', ''),
                        "description": getattr(col, 'description', '')
                    }
                    
                    table_info["columns"].append({
                        "name": col_data.get("name", ""),
                        "type": col_data.get("type", ""),
                        "description": col_data.get("description", "")
                    })
                
                indexed_data["tables_summary"].append(table_info)
            
            # Add all indexed documents with their content
            for i, doc in enumerate(documents, 1):
                doc_data = {
                    "document_id": i,
                    "content": doc.page_content,
                    "content_length": len(doc.page_content),
                    "metadata": doc.metadata
                }
                
                indexed_data["indexed_documents"].append(doc_data)
            
            # Save to JSON file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(indexed_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Saved indexed content dump to: {filepath}")
            logger.info(f"   📄 {len(documents)} documents indexed")
            logger.info(f"   📊 {len(schema.tables)} tables")
            
        except Exception as e:
            logger.error(f"Error saving indexed content dump: {str(e)}")
            # Don't fail the indexing if dump fails
    
    async def index_schema(self, request: IndexingRequest) -> IndexingResult:
        """Index a database schema."""
        try:
            logger.info(f"Indexing schema for database: {request.database_id}")
            
            # Convert schema to documents
            documents = self._schema_to_documents(request.db_schema, request.database_id)
            
            # Save indexed content to human-readable JSON file
            self._save_indexed_content_dump(request.database_id, documents, request.db_schema)
            
            # Create or update vector store
            if request.database_id in self.stores:
                # Update existing store
                self.stores[request.database_id].add_documents(documents)
            else:
                # Create new store
                self.stores[request.database_id] = FAISS.from_documents(
                    documents, 
                    self.embeddings
                )
            
            # Persist to disk
            store_path = self.vector_store_path / request.database_id
            self.stores[request.database_id].save_local(str(store_path))
            
            logger.info(f"Successfully indexed {len(documents)} documents for {request.database_id}")
            
            return IndexingResult(
                database_id=request.database_id,
                status="success",
                num_tables=len(request.db_schema.tables)
            )
            
        except Exception as e:
            logger.error(f"Error indexing schema: {str(e)}")
            return IndexingResult(
                database_id=request.database_id,
                status="failed",
                num_tables=0,
                error=str(e)
            )
    
    def load_index(self, database_id: str) -> bool:
        """Load an existing index from disk."""
        try:
            store_path = self.vector_store_path / database_id
            if store_path.exists():
                self.stores[database_id] = FAISS.load_local(
                    str(store_path),
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"Loaded index for database: {database_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error loading index: {str(e)}")
            return False
    
    def retrieve_context(self, database_id: str, query: str, k: int = 5) -> List[Document]:
        """Retrieve relevant schema context for a query."""
        if database_id not in self.stores:
            if not self.load_index(database_id):
                return []
        
        try:
            docs = self.stores[database_id].similarity_search(query, k=k)
            return docs
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            return []
    
    def delete_index(self, database_id: str) -> bool:
        """Delete an indexed database (remove from memory and disk)."""
        try:
            # Remove from memory
            if database_id in self.stores:
                del self.stores[database_id]
                logger.info(f"Removed {database_id} from memory")
            
            # Remove from disk
            store_path = self.vector_store_path / database_id
            if store_path.exists():
                import shutil
                shutil.rmtree(store_path)
                logger.info(f"Deleted index files for database: {database_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error deleting index for {database_id}: {str(e)}")
            return False
    
    def index_knowledge_base_instruction(
        self,
        database_id: str,
        instruction_id: str,
        title: str,
        content: str
    ) -> bool:
        """Add a knowledge base instruction to the vector store."""
        try:
            # Ensure store is loaded
            if database_id not in self.stores:
                if not self.load_index(database_id):
                    logger.error(f"No index found for database: {database_id}")
                    return False
            
            # Create document for the instruction
            text = f"INSTRUCTION: {title}\n\n{content}"
            
            metadata = {
                "database_id": database_id,
                "type": "instruction",
                "instruction_id": instruction_id,
                "title": title
            }
            
            doc = Document(page_content=text, metadata=metadata)
            
            # Add to vector store
            self.stores[database_id].add_documents([doc])
            
            # Persist to disk
            store_path = self.vector_store_path / database_id
            self.stores[database_id].save_local(str(store_path))
            
            logger.info(f"Indexed instruction {instruction_id} for {database_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing instruction: {str(e)}")
            return False
    
    def index_knowledge_base_sql_pair(
        self,
        database_id: str,
        pair_id: str,
        question: str,
        sql: str,
        description: Optional[str] = None
    ) -> bool:
        """Add a knowledge base SQL pair to the vector store."""
        try:
            # Ensure store is loaded
            if database_id not in self.stores:
                if not self.load_index(database_id):
                    logger.error(f"No index found for database: {database_id}")
                    return False
            
            # Create document for the SQL pair
            text = f"EXAMPLE QUERY:\nQuestion: {question}\nSQL: {sql}"
            if description:
                text += f"\nExplanation: {description}"
            
            metadata = {
                "database_id": database_id,
                "type": "sql_pair",
                "pair_id": pair_id,
                "question": question,
                "sql": sql
            }
            
            doc = Document(page_content=text, metadata=metadata)
            
            # Add to vector store
            self.stores[database_id].add_documents([doc])
            
            # Persist to disk
            store_path = self.vector_store_path / database_id
            self.stores[database_id].save_local(str(store_path))
            
            logger.info(f"Indexed SQL pair {pair_id} for {database_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing SQL pair: {str(e)}")
            return False


"""
Knowledge Base service for storing and retrieving instructions and SQL pairs.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from models import (
    KnowledgeBaseInstruction,
    KnowledgeBaseSQLPair,
    KnowledgeBaseType
)

logger = logging.getLogger(__name__)


class KnowledgeBaseStore:
    """Store and retrieve knowledge base entries in SQLite."""
    
    def __init__(self, db_path: str = "./data/knowledge_base.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with knowledge base tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Instructions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS instructions (
                id TEXT PRIMARY KEY,
                database_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # SQL Pairs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sql_pairs (
                id TEXT PRIMARY KEY,
                database_id TEXT NOT NULL,
                question TEXT NOT NULL,
                sql TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_instructions_db ON instructions(database_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sql_pairs_db ON sql_pairs(database_id)")
        
        conn.commit()
        conn.close()
        logger.info(f"Knowledge base database initialized at {self.db_path}")
    
    def add_instruction(
        self, 
        database_id: str, 
        title: str, 
        content: str
    ) -> KnowledgeBaseInstruction:
        """Add a new instruction."""
        try:
            instruction_id = f"inst_{datetime.now().timestamp()}"
            created_at = datetime.now()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO instructions (id, database_id, title, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (instruction_id, database_id, title, content, created_at.isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added instruction {instruction_id} for database {database_id}")
            
            return KnowledgeBaseInstruction(
                id=instruction_id,
                database_id=database_id,
                title=title,
                content=content,
                created_at=created_at
            )
            
        except Exception as e:
            logger.error(f"Error adding instruction: {str(e)}")
            raise
    
    def add_sql_pair(
        self,
        database_id: str,
        question: str,
        sql: str,
        description: Optional[str] = None
    ) -> KnowledgeBaseSQLPair:
        """Add a new SQL pair."""
        try:
            pair_id = f"pair_{datetime.now().timestamp()}"
            created_at = datetime.now()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sql_pairs (id, database_id, question, sql, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pair_id, database_id, question, sql, description, created_at.isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added SQL pair {pair_id} for database {database_id}")
            
            return KnowledgeBaseSQLPair(
                id=pair_id,
                database_id=database_id,
                question=question,
                sql=sql,
                description=description,
                created_at=created_at
            )
            
        except Exception as e:
            logger.error(f"Error adding SQL pair: {str(e)}")
            raise
    
    def get_instructions(self, database_id: str) -> List[KnowledgeBaseInstruction]:
        """Get all instructions for a database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, database_id, title, content, created_at
                FROM instructions
                WHERE database_id = ?
                ORDER BY created_at DESC
            """, (database_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            instructions = []
            for row in rows:
                instructions.append(KnowledgeBaseInstruction(
                    id=row[0],
                    database_id=row[1],
                    title=row[2],
                    content=row[3],
                    created_at=datetime.fromisoformat(row[4])
                ))
            
            return instructions
            
        except Exception as e:
            logger.error(f"Error getting instructions: {str(e)}")
            return []
    
    def get_sql_pairs(self, database_id: str) -> List[KnowledgeBaseSQLPair]:
        """Get all SQL pairs for a database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, database_id, question, sql, description, created_at
                FROM sql_pairs
                WHERE database_id = ?
                ORDER BY created_at DESC
            """, (database_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            pairs = []
            for row in rows:
                pairs.append(KnowledgeBaseSQLPair(
                    id=row[0],
                    database_id=row[1],
                    question=row[2],
                    sql=row[3],
                    description=row[4],
                    created_at=datetime.fromisoformat(row[5])
                ))
            
            return pairs
            
        except Exception as e:
            logger.error(f"Error getting SQL pairs: {str(e)}")
            return []
    
    def delete_instruction(self, instruction_id: str) -> bool:
        """Delete an instruction."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM instructions WHERE id = ?", (instruction_id,))
            
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            
            if deleted:
                logger.info(f"Deleted instruction {instruction_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting instruction: {str(e)}")
            return False
    
    def delete_sql_pair(self, pair_id: str) -> bool:
        """Delete a SQL pair."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM sql_pairs WHERE id = ?", (pair_id,))
            
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            
            if deleted:
                logger.info(f"Deleted SQL pair {pair_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting SQL pair: {str(e)}")
            return False


# Global instance
knowledge_base_store = KnowledgeBaseStore()

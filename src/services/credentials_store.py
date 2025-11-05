"""
Database credentials storage using SQLite.
Stores MySQL connection credentials securely (password encrypted).
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
from cryptography.fernet import Fernet
import os

from models import DatabaseInfo

logger = logging.getLogger(__name__)


class CredentialsStore:
    """Store and retrieve database credentials in SQLite."""
    
    def __init__(self, db_path: str = "./data/credentials.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption key (store in env or generate once)
        self._init_encryption_key()
        
        # Initialize database
        self._init_db()
    
    def _init_encryption_key(self):
        """Initialize or load encryption key."""
        key_file = self.db_path.parent / ".encryption_key"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                self.cipher = Fernet(f.read())
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            self.cipher = Fernet(key)
            logger.info("Generated new encryption key")
    
    def _init_db(self):
        """Initialize SQLite database with credentials table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                database_id TEXT PRIMARY KEY,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                user TEXT NOT NULL,
                password_encrypted BLOB NOT NULL,
                database_name TEXT NOT NULL,
                selected_tables TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Credentials database initialized at {self.db_path}")
    
    def _encrypt_password(self, password: str) -> bytes:
        """Encrypt password."""
        return self.cipher.encrypt(password.encode())
    
    def _decrypt_password(self, encrypted: bytes) -> str:
        """Decrypt password."""
        return self.cipher.decrypt(encrypted).decode()
    
    def store_credentials(self, database_id: str, host: str, port: int, 
                         user: str, password: str, database_name: str,
                         selected_tables: Optional[List[str]] = None) -> bool:
        """Store database credentials and selected tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            encrypted_password = self._encrypt_password(password)
            tables_json = json.dumps(selected_tables) if selected_tables else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO credentials 
                (database_id, host, port, user, password_encrypted, database_name, selected_tables, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (database_id, host, port, user, encrypted_password, database_name, tables_json))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Stored credentials for database: {database_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing credentials: {str(e)}")
            return False
    
    def get_credentials(self, database_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve database credentials (with decrypted password)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT host, port, user, password_encrypted, database_name, selected_tables
                FROM credentials
                WHERE database_id = ?
            """, (database_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            selected_tables = json.loads(row[5]) if row[5] else None
            
            return {
                'host': row[0],
                'port': row[1],
                'user': row[2],
                'password': self._decrypt_password(row[3]),
                'database': row[4],
                'selected_tables': selected_tables
            }
            
        except Exception as e:
            logger.error(f"Error retrieving credentials: {str(e)}")
            return None
    
    def list_databases(self) -> List[DatabaseInfo]:
        """List all stored databases (without passwords)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT database_id, host, port, user, database_name, created_at
                FROM credentials
                ORDER BY database_id
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                DatabaseInfo(
                    database_id=row[0],
                    host=row[1],
                    port=row[2],
                    user=row[3],
                    database_name=row[4],
                    created_at=row[5]
                )
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Error listing databases: {str(e)}")
            return []
    
    def delete_credentials(self, database_id: str) -> bool:
        """Delete database credentials."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM credentials WHERE database_id = ?", (database_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Deleted credentials for database: {database_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting credentials: {str(e)}")
            return False
    
    def database_exists(self, database_id: str) -> bool:
        """Check if database credentials exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT 1 FROM credentials WHERE database_id = ?", 
                (database_id,)
            )
            
            exists = cursor.fetchone() is not None
            conn.close()
            
            return exists
            
        except Exception as e:
            logger.error(f"Error checking database existence: {str(e)}")
            return False


# Global instance
credentials_store = CredentialsStore()

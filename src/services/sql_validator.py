"""
SQL Query Validator - Security module to restrict query execution.

This module ensures that only safe, read-only queries are executed.
It blocks any destructive operations like INSERT, UPDATE, DELETE, DROP, etc.
"""

import re
from typing import Tuple, List
from enum import Enum


class QueryType(Enum):
    """Enumeration of query types."""
    SELECT = "SELECT"
    SHOW = "SHOW"
    DESCRIBE = "DESCRIBE"
    EXPLAIN = "EXPLAIN"
    UNSAFE = "UNSAFE"


class SQLValidationError(Exception):
    """Exception raised when a SQL query fails validation."""
    pass


class SQLValidator:
    """
    Validates SQL queries to ensure they are safe to execute.
    Only allows read-only operations.
    """
    
    # Allowed query types (read-only operations)
    ALLOWED_STATEMENTS = {
        'SELECT',
        'SHOW',
        'DESCRIBE',
        'DESC',
        'EXPLAIN',
        'WITH'  # Common Table Expressions with SELECT
    }
    
    # Forbidden query types (write/destructive operations)
    FORBIDDEN_STATEMENTS = {
        'INSERT',
        'UPDATE',
        'DELETE',
        'DROP',
        'CREATE',
        'ALTER',
        'TRUNCATE',
        'REPLACE',
        'RENAME',
        'GRANT',
        'REVOKE',
        'CALL',
        'EXECUTE',
        'LOAD',
        'LOCK',
        'UNLOCK',
        'SET',
        'START',
        'COMMIT',
        'ROLLBACK',
        'SAVEPOINT',
        'USE'
    }
    
    # Dangerous SQL patterns that might bypass basic checks
    DANGEROUS_PATTERNS = [
        r';\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)',  # Multiple statements
        r'INTO\s+OUTFILE',  # File operations
        r'INTO\s+DUMPFILE',
        r'LOAD_FILE',
        r'--\s*$',  # SQL comments at end (might hide dangerous code)
        r'/\*.*?\*/',  # Block comments
    ]
    
    @classmethod
    def validate(cls, query: str) -> Tuple[bool, str]:
        """
        Validate if a SQL query is safe to execute.
        
        Args:
            query: The SQL query to validate
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if query is safe, False otherwise
            - error_message: Empty string if valid, error description if invalid
            
        Raises:
            SQLValidationError: If the query is not safe to execute
        """
        if not query or not query.strip():
            return False, "Empty query provided"
        
        # Normalize query: remove extra whitespace and convert to uppercase for checking
        normalized_query = ' '.join(query.strip().split()).upper()
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE | re.DOTALL):
                error = f"Query contains forbidden pattern: {pattern}"
                return False, error
        
        # Extract the first statement type
        first_word = normalized_query.split()[0] if normalized_query else ""
        
        # Check if it's a forbidden statement
        if first_word in cls.FORBIDDEN_STATEMENTS:
            error = f"Query type '{first_word}' is not allowed. Only SELECT and discovery queries are permitted."
            return False, error
        
        # Check if it's an allowed statement
        if first_word not in cls.ALLOWED_STATEMENTS:
            error = f"Unknown or unsupported query type '{first_word}'. Only SELECT and discovery queries are permitted."
            return False, error
        
        # Additional check: if it's a WITH clause, ensure it's followed by SELECT
        if first_word == 'WITH':
            if not re.search(r'\bSELECT\b', normalized_query):
                error = "WITH clause must be followed by a SELECT statement"
                return False, error
            # Check that no forbidden statements appear after WITH
            for forbidden in cls.FORBIDDEN_STATEMENTS:
                if re.search(rf'\b{forbidden}\b', normalized_query):
                    error = f"WITH clause contains forbidden statement: {forbidden}"
                    return False, error
        
        # Check for multiple statements (basic check)
        if ';' in query.rstrip(';'):  # Allow single trailing semicolon
            error = "Multiple statements are not allowed"
            return False, error
        
        return True, ""
    
    @classmethod
    def validate_and_raise(cls, query: str) -> None:
        """
        Validate a query and raise an exception if invalid.
        
        Args:
            query: The SQL query to validate
            
        Raises:
            SQLValidationError: If the query is not safe to execute
        """
        is_valid, error_message = cls.validate(query)
        if not is_valid:
            raise SQLValidationError(error_message)
    
    @classmethod
    def get_query_type(cls, query: str) -> QueryType:
        """
        Determine the type of a SQL query.
        
        Args:
            query: The SQL query to analyze
            
        Returns:
            QueryType enum value
        """
        if not query or not query.strip():
            return QueryType.UNSAFE
        
        normalized_query = query.strip().upper()
        first_word = normalized_query.split()[0] if normalized_query else ""
        
        if first_word in cls.FORBIDDEN_STATEMENTS:
            return QueryType.UNSAFE
        elif first_word == 'SELECT' or first_word == 'WITH':
            return QueryType.SELECT
        elif first_word == 'SHOW':
            return QueryType.SHOW
        elif first_word in ['DESCRIBE', 'DESC']:
            return QueryType.DESCRIBE
        elif first_word == 'EXPLAIN':
            return QueryType.EXPLAIN
        else:
            return QueryType.UNSAFE
    
    @classmethod
    def sanitize_query(cls, query: str) -> str:
        """
        Sanitize a query by removing comments and extra whitespace.
        
        Args:
            query: The SQL query to sanitize
            
        Returns:
            Sanitized query string
        """
        # Remove SQL comments
        query = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        return query.strip()
    
    @classmethod
    def is_read_only(cls, query: str) -> bool:
        """
        Quick check if a query is read-only.
        
        Args:
            query: The SQL query to check
            
        Returns:
            True if query is read-only, False otherwise
        """
        is_valid, _ = cls.validate(query)
        return is_valid


# Convenience function for quick validation
def validate_sql_query(query: str) -> Tuple[bool, str]:
    """
    Convenience function to validate a SQL query.
    
    Args:
        query: The SQL query to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    return SQLValidator.validate(query)

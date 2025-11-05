"""
SQL Generation pipeline - converts natural language to SQL.
"""

import logging
from typing import Optional, Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from models import QueryRequest, SQLResult, QueryStatus
from pipelines.indexing import SchemaIndexer
from services.sql_validator import SQLValidator, SQLValidationError
from config import settings

logger = logging.getLogger(__name__)


SQL_GENERATION_PROMPT = """You are an expert SQL query generator. Given a natural language question and database schema context, generate a valid SQL query.

Database Schema Context:
{schema_context}

User Question: {question}

Query Plan:
{reasoning}

Instructions:
1. Follow the query plan provided above
2. Generate a syntactically correct SQL query that answers the user's question
3. Use only the tables and columns provided in the schema context
4. Be precise with column names and table names (case-sensitive)
5. **IMPORTANT**: Use the foreign key relationships provided in the schema context to JOIN tables correctly
6. When joining tables, always use the relationships shown in the "DATABASE RELATIONSHIPS" section
7. Add appropriate WHERE clauses, GROUP BY, ORDER BY as needed
8. **SECURITY**: Generate ONLY read-only queries (SELECT, SHOW, DESCRIBE, EXPLAIN). DO NOT generate INSERT, UPDATE, DELETE, DROP, or any other data modification queries.
9. Return ONLY the SQL query without any explanation or markdown formatting

SQL Query:"""


REASONING_PROMPT = """You are an expert database analyst. Analyze the user's question and the available database schema, then create a detailed step-by-step plan for generating the SQL query.

Database Schema Context:
{schema_context}

User Question: {question}

**IMPORTANT**: Provide ONLY high-level analysis and planning. Do NOT write any SQL code in your response.

Please analyze:
1. **Intent Analysis**: What is the user trying to find out? What type of question is this (aggregation, filtering, joining, etc.)?
2. **Required Tables**: Which tables from the schema are needed to answer this question? Why these tables?
3. **Required Columns**: Which specific columns do we need to select or filter? List them clearly.
4. **Relationships & JOINs**: **CRITICAL** - Look at the "DATABASE RELATIONSHIPS" section in the schema. Which foreign keys should be used? Describe the join conditions needed (in plain language, not SQL).
5. **Filtering**: What WHERE conditions are needed based on the question? Describe them conceptually.
6. **Aggregation**: Does the question require GROUP BY, COUNT, SUM, AVG, etc.? What should be aggregated?
7. **Sorting/Limiting**: Should results be sorted? By which column(s)? Is a limit needed?
8. **Step-by-Step Plan**: Provide a clear conceptual plan for constructing the query, describing each step in plain language.
9. **Output Columns**: What columns should be included in the final output to be relevant to the user's question? Prefer human-readable fields over IDs.

Remember: This is a planning phase. Describe what needs to be done, but do NOT write SQL syntax. The actual SQL will be generated in the next step based on your analysis.

Analysis and Plan:"""


EXPLANATION_PROMPT = """Given this SQL query and the user's question, provide a brief explanation of what the query does.

User Question: {question}
SQL Query: {sql}

Provide a concise explanation in 2-3 sentences of what this query does and what results it will return.

Explanation:"""


RESULT_ANALYSIS_PROMPT = """Given a user's question, the SQL query that was executed, and the results, provide a clear and concise natural language answer.

User Question: {question}

SQL Query:
{sql}

Query Results:
{results}

Total Rows: {row_count}

Please provide a natural language answer that:
1. Directly answers the user's question based on the results
2. Highlights key findings or patterns in the data
3. Is concise but informative (2-4 sentences)
4. Uses natural language, not technical jargon

Natural Language Answer:"""


SQL_FIX_PROMPT = """You are an expert SQL debugger. A SQL query has failed with an error. Analyze the error and fix the query.

Database Schema Context:
{schema_context}

Original User Question: {question}

Previous Query (FAILED):
{failed_sql}

Error Message:
{error_message}

Previous Fix Attempts: {attempt_number}/5
{previous_attempts}

Instructions:
1. Carefully analyze the error message
2. Identify the specific issue (syntax error, wrong column name, missing JOIN, etc.)
3. Review the schema context to ensure correct table/column names
4. Fix ONLY the specific issue - don't change the query logic unnecessarily
5. Common issues to check:
   - Column names (case-sensitive, check schema)
   - Table names (case-sensitive, check schema)
   - Missing JOINs when referencing multiple tables
   - Syntax errors (missing commas, parentheses, quotes)
   - Ambiguous column names (need table prefix)
   - Wrong aggregate functions or GROUP BY clauses
6. Return ONLY the fixed SQL query without any explanation or markdown formatting

Fixed SQL Query:"""


class SQLGenerator:
    """
    Generates SQL queries from natural language questions.
    Uses LangChain for LLM integration and retrieval.
    """
    
    def __init__(self, indexer: SchemaIndexer):
        self.indexer = indexer
        
        # Initialize LLM with optional base_url for local models
        llm_kwargs = {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        }
        
        # Add API key if provided (optional for local models)
        if settings.llm_api_key:
            llm_kwargs["api_key"] = settings.llm_api_key
        
        # Add base_url for local LLMs (e.g., Ollama, LM Studio, LocalAI)
        if settings.llm_base_url:
            llm_kwargs["base_url"] = settings.llm_base_url
            logger.info(f"Using custom LLM endpoint: {settings.llm_base_url}")
        
        self.llm = ChatOpenAI(**llm_kwargs)
        
        # Create prompts
        self.reasoning_prompt = ChatPromptTemplate.from_template(REASONING_PROMPT)
        self.sql_prompt = ChatPromptTemplate.from_template(SQL_GENERATION_PROMPT)
        self.explanation_prompt = ChatPromptTemplate.from_template(EXPLANATION_PROMPT)
        self.result_analysis_prompt = ChatPromptTemplate.from_template(RESULT_ANALYSIS_PROMPT)
        self.sql_fix_prompt = ChatPromptTemplate.from_template(SQL_FIX_PROMPT)
        
        # Create chains
        self.reasoning_chain = self.reasoning_prompt | self.llm | StrOutputParser()
        self.sql_chain = self.sql_prompt | self.llm | StrOutputParser()
        self.explanation_chain = self.explanation_prompt | self.llm | StrOutputParser()
        self.result_analysis_chain = self.result_analysis_prompt | self.llm | StrOutputParser()
        self.sql_fix_chain = self.sql_fix_prompt | self.llm | StrOutputParser()
        
    async def generate_sql(self, request: QueryRequest) -> SQLResult:
        """Generate SQL from natural language question with step-by-step reasoning."""
        try:
            logger.info(f"Generating SQL for query: {request.query_id}")
            
            # Step 1: Retrieve relevant schema context
            schema_docs = self.indexer.retrieve_context(
                request.database_id, 
                request.question,
                k=10
            )
            
            if not schema_docs:
                return SQLResult(
                    query_id=request.query_id,
                    status=QueryStatus.FAILED,
                    error=f"No schema found for database: {request.database_id}"
                )
            
            # Format schema context
            schema_context = self._format_schema_context(schema_docs)
            
            logger.info(f"Retrieved {len(schema_docs)} relevant schema documents")
            
            # Step 2: Generate reasoning/plan
            logger.info("Generating query plan and reasoning...")
            reasoning = await self.reasoning_chain.ainvoke({
                "schema_context": schema_context,
                "question": request.question
            })
            reasoning = reasoning.strip()
            
            logger.info(f"Generated reasoning: {reasoning[:200]}...")
            
            # Step 3: Generate SQL using LLM with reasoning
            logger.info("Generating SQL query based on plan...")
            sql = await self.sql_chain.ainvoke({
                "schema_context": schema_context,
                "question": request.question,
                "reasoning": reasoning
            })
            
            # Clean up SQL (remove markdown, extra whitespace)
            sql = self._clean_sql(sql)
            
            # Validate SQL for security
            is_valid, validation_error = SQLValidator.validate(sql)
            if not is_valid:
                logger.error(f"Generated SQL failed validation: {validation_error}")
                return SQLResult(
                    query_id=request.query_id,
                    status=QueryStatus.FAILED,
                    error=f"Generated query is not allowed: {validation_error}. Only SELECT and discovery queries are permitted."
                )
            
            logger.info(f"Generated SQL: {sql[:100]}...")

            
            # Step 4: Generate explanation
            explanation = await self.explanation_chain.ainvoke({
                "question": request.question,
                "sql": sql
            })
            
            return SQLResult(
                query_id=request.query_id,
                status=QueryStatus.COMPLETED,
                sql=sql,
                explanation=explanation.strip(),
                reasoning=reasoning,
                metadata={
                    "num_schema_docs": len(schema_docs),
                    "model": settings.llm_model
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            return SQLResult(
                query_id=request.query_id,
                status=QueryStatus.FAILED,
                error=str(e)
            )
    
    def _format_schema_context(self, docs) -> str:
        """Format retrieved documents into schema context."""
        context_parts = []
        
        # Separate documents by type
        tables = {}
        relationships = []
        instructions = []
        sql_pairs = []
        other = []
        
        for doc in docs:
            doc_type = doc.metadata.get("type")
            
            if doc_type == "relationships":
                relationships.append(doc)
            elif doc_type == "instruction":
                instructions.append(doc)
            elif doc_type == "sql_pair":
                sql_pairs.append(doc)
            elif doc_type in ["table", "column"]:
                table_name = doc.metadata.get("table_name")
                if table_name:
                    if table_name not in tables:
                        tables[table_name] = []
                    tables[table_name].append(doc)
                else:
                    other.append(doc)
            else:
                other.append(doc)
        
        # Format relationships first (important for JOINs)
        if relationships:
            context_parts.append("=" * 60)
            context_parts.append("DATABASE RELATIONSHIPS")
            context_parts.append("=" * 60)
            for doc in relationships:
                context_parts.append(doc.page_content)
        
        # Format instructions (domain knowledge)
        if instructions:
            context_parts.append("\n" + "=" * 60)
            context_parts.append("DOMAIN KNOWLEDGE & INSTRUCTIONS")
            context_parts.append("=" * 60)
            for doc in instructions:
                context_parts.append(doc.page_content)
        
        # Format SQL pairs (example queries)
        if sql_pairs:
            context_parts.append("\n" + "=" * 60)
            context_parts.append("EXAMPLE QUERIES (Similar to this question)")
            context_parts.append("=" * 60)
            for doc in sql_pairs:
                context_parts.append(doc.page_content)
        
        # Format tables and columns
        if tables:
            context_parts.append("\n" + "=" * 60)
            context_parts.append("DATABASE SCHEMA")
            context_parts.append("=" * 60)
            for table_name, table_docs in tables.items():
                context_parts.append(f"\n--- Table: {table_name} ---")
                for doc in table_docs:
                    context_parts.append(doc.page_content)
        
        # Add any other documents
        if other:
            for doc in other:
                context_parts.append(doc.page_content)
        
        return "\n".join(context_parts)
    
    def _clean_sql(self, sql: str) -> str:
        """Clean up generated SQL."""
        # Remove markdown code blocks
        sql = sql.replace("```sql", "").replace("```", "")
        
        # Remove extra whitespace
        sql = sql.strip()
        
        # Ensure it ends with semicolon
        if not sql.endswith(";"):
            sql += ";"
        
        return sql
    
    async def analyze_results(
        self, 
        question: str, 
        sql: str, 
        results: List[Dict[str, Any]],
        row_count: int
    ) -> str:
        """
        Generate natural language explanation of query results.
        
        Args:
            question: Original user question
            sql: SQL query that was executed
            results: Query results (list of dicts)
            row_count: Number of rows returned
            
        Returns:
            Natural language answer
        """
        try:
            # Format results for prompt (limit to first 10 rows for context)
            sample_results = results[:10] if results else []
            results_text = "\n".join([str(row) for row in sample_results])
            
            if len(results) > 10:
                results_text += f"\n... (showing 10 of {len(results)} rows)"
            
            # Generate natural language answer
            answer = await self.result_analysis_chain.ainvoke({
                "question": question,
                "sql": sql,
                "results": results_text,
                "row_count": row_count
            })
            
            return answer.strip()
            
        except Exception as e:
            logger.error(f"Error analyzing results: {str(e)}")
            return f"Query returned {row_count} rows. Unable to generate detailed analysis."
    
    async def fix_sql(
        self,
        question: str,
        failed_sql: str,
        error_message: str,
        schema_context: str,
        reasoning: str,
        attempt_number: int,
        previous_attempts: List[Dict[str, str]]
    ) -> str:
        """
        Attempt to fix a failed SQL query.
        
        Args:
            question: Original user question
            failed_sql: The SQL query that failed
            error_message: The error message from the database
            schema_context: Database schema context
            reasoning: Original query plan/reasoning
            attempt_number: Current attempt number (1-5)
            previous_attempts: List of previous fix attempts with errors
            
        Returns:
            Fixed SQL query
        """
        try:
            logger.info(f"Attempting to fix SQL (attempt {attempt_number}/5)")
            logger.info(f"Error: {error_message[:200]}")
            
            # Format previous attempts
            previous_attempts_text = ""
            if previous_attempts:
                previous_attempts_text = "\n\nPrevious failed attempts:"
                for i, attempt in enumerate(previous_attempts, 1):
                    previous_attempts_text += f"\n\nAttempt {i}:\nSQL: {attempt['sql']}\nError: {attempt['error']}"
            
            # Generate fixed SQL
            fixed_sql = await self.sql_fix_chain.ainvoke({
                "schema_context": schema_context,
                "question": question,
                "failed_sql": failed_sql,
                "error_message": error_message,
                "reasoning": reasoning,
                "attempt_number": attempt_number,
                "previous_attempts": previous_attempts_text
            })
            
            # Clean up SQL
            fixed_sql = self._clean_sql(fixed_sql)
            
            # Validate the fixed SQL
            is_valid, validation_error = SQLValidator.validate(fixed_sql)
            if not is_valid:
                logger.warning(f"Fixed SQL failed validation: {validation_error}")
                # Return the failed SQL so the error can be reported properly
                return failed_sql
            
            logger.info(f"Generated fix: {fixed_sql[:100]}...")

            
            return fixed_sql
            
        except Exception as e:
            logger.error(f"Error in fix_sql: {str(e)}")
            # Return original SQL if fix fails
            return failed_sql



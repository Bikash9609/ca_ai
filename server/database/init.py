"""
Database initialization for rules server
"""

import logging
from pathlib import Path
from server.database.connection import DatabasePool

logger = logging.getLogger(__name__)


async def initialize_database(pool: DatabasePool, schema_file: Path) -> None:
    """Initialize database schema from SQL file"""
    logger.info("Initializing database schema...")
    
    with open(schema_file, "r") as f:
        schema_sql = f.read()
    
    # Execute schema
    await pool.execute(schema_sql)
    
    logger.info("Database schema initialized successfully")


async def check_database_connection(pool: DatabasePool) -> bool:
    """Check if database connection is working"""
    try:
        result = await pool.fetchval("SELECT 1")
        return result == 1
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def check_pgvector_extension(pool: DatabasePool) -> bool:
    """Check if pgvector extension is installed"""
    try:
        result = await pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        )
        return result is True
    except Exception as e:
        logger.error(f"pgvector check failed: {e}")
        return False

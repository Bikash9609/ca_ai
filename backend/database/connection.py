"""
SQLite database connection management
"""

import aiosqlite
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database connections"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self) -> None:
        """Create database connection"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(
                str(self.db_path),
                isolation_level=None  # Autocommit mode
            )
            # Enable WAL mode for better concurrency
            await self._connection.execute("PRAGMA journal_mode=WAL")
            # Set cache size for better performance
            await self._connection.execute("PRAGMA cache_size=-64000")  # 64MB cache
            # Enable foreign keys
            await self._connection.execute("PRAGMA foreign_keys=ON")
            logger.info(f"Connected to database: {self.db_path}")
    
    async def disconnect(self) -> None:
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Disconnected from database")
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get database connection"""
        if self._connection is None:
            await self.connect()
        return self._connection
    
    async def execute(self, query: str, params: Optional[tuple] = None) -> aiosqlite.Cursor:
        """Execute a query"""
        conn = await self.get_connection()
        return await conn.execute(query, params or ())
    
    async def executemany(self, query: str, params_list: list[tuple]) -> aiosqlite.Cursor:
        """Execute a query multiple times"""
        conn = await self.get_connection()
        return await conn.executemany(query, params_list)
    
    async def fetchone(self, query: str, params: Optional[tuple] = None) -> Optional[tuple]:
        """Fetch one row"""
        conn = await self.get_connection()
        cursor = await conn.execute(query, params or ())
        return await cursor.fetchone()
    
    async def fetchall(self, query: str, params: Optional[tuple] = None) -> list[tuple]:
        """Fetch all rows"""
        conn = await self.get_connection()
        cursor = await conn.execute(query, params or ())
        return await cursor.fetchall()
    
    async def initialize_schema(self, schema_file: Path) -> None:
        """Initialize database schema from SQL file"""
        conn = await self.get_connection()
        with open(schema_file, "r") as f:
            schema_sql = f.read()
        
        # Execute schema (SQLite doesn't support multiple statements in execute)
        # Split by semicolon and execute each statement
        statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
        for statement in statements:
            if statement:  # Skip empty statements
                await conn.execute(statement)
        
        await conn.commit()
        logger.info("Database schema initialized")
    
    async def run_migrations(self, migrations_dir: Path) -> None:
        """Run database migrations"""
        from database.migrations.migration_manager import MigrationManager
        
        migration_manager = MigrationManager(self.db_path, migrations_dir)
        await migration_manager.migrate()
        logger.info("Database migrations completed")

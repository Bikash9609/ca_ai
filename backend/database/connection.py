"""
SQLite database connection management
"""

import aiosqlite
from pathlib import Path
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database connections"""
    
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None
        self._schema_initialized = False
    
    async def connect(self) -> None:
        """Create database connection"""
        if self._connection is None:
            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Connect with timeout to handle locking
            self._connection = await aiosqlite.connect(
                str(self.db_path),
                isolation_level=None,  # Autocommit mode
                timeout=30.0  # 30 second timeout for locked database
            )
            # Enable WAL mode for better concurrency
            await self._connection.execute("PRAGMA journal_mode=WAL")
            # Set cache size for better performance
            await self._connection.execute("PRAGMA cache_size=-64000")  # 64MB cache
            # Enable foreign keys
            await self._connection.execute("PRAGMA foreign_keys=ON")
            # Set busy timeout
            await self._connection.execute("PRAGMA busy_timeout=30000")  # 30 seconds
            logger.info(f"Connected to database: {self.db_path}")
            
            # Initialize schema if needed
            await self._ensure_schema()
    
    async def disconnect(self) -> None:
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Disconnected from database")
    
    async def _ensure_schema(self) -> None:
        """Ensure database schema is initialized"""
        if self._schema_initialized:
            return
        
        # Check if documents table exists
        cursor = await self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
        )
        table_exists = await cursor.fetchone()
        
        migrations_dir = Path(__file__).parent / "migrations"
        schema_file = Path(__file__).parent / "schema.sql"

        # Always run migrations when available so newer tables (e.g., conversations)
        # are added even on already-initialized databases.
        if migrations_dir.exists():
            await self.run_migrations(migrations_dir)
        elif not table_exists and schema_file.exists():
            logger.info("Initializing database schema...")
            await self.initialize_schema(schema_file)
        
        self._schema_initialized = True
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get database connection"""
        if self._connection is None:
            await self.connect()
        return self._connection
    
    async def execute(self, query: str, params: Optional[tuple] = None) -> aiosqlite.Cursor:
        """Execute a query"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn = await self.get_connection()
                return await conn.execute(query, params or ())
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise
    
    async def executemany(self, query: str, params_list: list[tuple]) -> aiosqlite.Cursor:
        """Execute a query multiple times"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn = await self.get_connection()
                return await conn.executemany(query, params_list)
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise
    
    async def fetchone(self, query: str, params: Optional[tuple] = None) -> Optional[tuple]:
        """Fetch one row"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn = await self.get_connection()
                cursor = await conn.execute(query, params or ())
                return await cursor.fetchone()
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise
    
    async def fetchall(self, query: str, params: Optional[tuple] = None) -> list[tuple]:
        """Fetch all rows"""
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn = await self.get_connection()
                cursor = await conn.execute(query, params or ())
                return await cursor.fetchall()
            except Exception as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise
    
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
        
        # In autocommit mode, commit is not needed but doesn't hurt
        try:
            await conn.commit()
        except Exception:
            pass  # Ignore if autocommit mode
        logger.info("Database schema initialized")
    
    async def run_migrations(self, migrations_dir: Path) -> None:
        """Run database migrations"""
        from database.migrations.migration_manager import MigrationManager
        
        migration_manager = MigrationManager(self.db_path, migrations_dir)
        await migration_manager.migrate()
        logger.info("Database migrations completed")

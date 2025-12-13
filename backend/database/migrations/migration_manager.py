"""
Database migration manager
"""

import aiosqlite
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages database migrations"""
    
    def __init__(self, db_path: Path, migrations_dir: Path):
        self.db_path = db_path
        self.migrations_dir = migrations_dir
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_migrations_table(self, conn: aiosqlite.Connection) -> None:
        """Create migrations tracking table"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()
    
    async def get_applied_migrations(self, conn: aiosqlite.Connection) -> List[str]:
        """Get list of applied migrations"""
        await self.create_migrations_table(conn)
        cursor = await conn.execute("SELECT version FROM migrations ORDER BY applied_at")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
    
    async def apply_migration(self, conn: aiosqlite.Connection, version: str, sql: str) -> None:
        """Apply a migration"""
        try:
            # Check if migration already applied
            cursor = await conn.execute(
                "SELECT version FROM migrations WHERE version = ?",
                (version,)
            )
            existing = await cursor.fetchone()
            if existing:
                logger.info(f"Migration {version} already applied, skipping")
                return
            
            # Execute migration
            await conn.executescript(sql)
            # Record migration
            await conn.execute(
                "INSERT INTO migrations (version) VALUES (?)",
                (version,)
            )
            await conn.commit()
            logger.info(f"Applied migration: {version}")
        except Exception as e:
            await conn.rollback()
            logger.error(f"Failed to apply migration {version}: {e}")
            raise
    
    async def migrate(self) -> None:
        """Run all pending migrations"""
        async with aiosqlite.connect(str(self.db_path)) as conn:
            applied = await self.get_applied_migrations(conn)
            
            # Get all migration files
            migration_files = sorted(self.migrations_dir.glob("*.sql"))
            
            for migration_file in migration_files:
                version = migration_file.stem
                if version not in applied:
                    logger.info(f"Applying migration: {version}")
                    with open(migration_file, "r") as f:
                        sql = f.read()
                    await self.apply_migration(conn, version, sql)

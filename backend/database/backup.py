"""
Database backup and restore utilities
"""

import aiosqlite
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages database backups"""
    
    def __init__(self, db_path: Path, backup_dir: Path):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self, suffix: Optional[str] = None) -> Path:
        """Create a backup of the database"""
        if suffix is None:
            suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        backup_path = self.backup_dir / f"backup_{suffix}.db"
        
        # Use SQLite backup API for online backup
        async with aiosqlite.connect(str(self.db_path)) as source:
            async with aiosqlite.connect(str(backup_path)) as backup:
                await source.backup(backup)
        
        logger.info(f"Created backup: {backup_path}")
        return backup_path
    
    async def restore_backup(self, backup_path: Path) -> None:
        """Restore database from backup"""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        # Close any existing connections
        # Create a temporary backup of current DB
        temp_backup = self.db_path.with_suffix(".db.bak")
        if self.db_path.exists():
            shutil.copy2(self.db_path, temp_backup)
        
        try:
            # Restore from backup
            async with aiosqlite.connect(str(backup_path)) as source:
                async with aiosqlite.connect(str(self.db_path)) as target:
                    await source.backup(target)
            
            logger.info(f"Restored database from: {backup_path}")
        except Exception as e:
            # Restore from temp backup on failure
            if temp_backup.exists():
                shutil.copy2(temp_backup, self.db_path)
            logger.error(f"Restore failed, reverted: {e}")
            raise
    
    def list_backups(self) -> list[Path]:
        """List all available backups"""
        return sorted(self.backup_dir.glob("backup_*.db"), reverse=True)
    
    def cleanup_old_backups(self, keep_count: int = 10) -> None:
        """Remove old backups, keeping only the most recent ones"""
        backups = self.list_backups()
        if len(backups) > keep_count:
            for backup in backups[keep_count:]:
                backup.unlink()
                logger.info(f"Removed old backup: {backup}")

"""
Version management API routes
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from server.database.connection import DatabasePool


def get_db_pool() -> DatabasePool:
    """Dependency to get database pool"""
    from server.main import db_pool
    if db_pool is None:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
    return db_pool

router = APIRouter()


class VersionResponse(BaseModel):
    id: int
    version: str
    released_at: datetime
    changelog: Optional[str]
    rules_count: Optional[int]


@router.get("/versions", response_model=List[VersionResponse])
async def get_versions(pool: DatabasePool = Depends(get_db_pool)):
    """Get all rule versions"""
    
    rows = await pool.fetch(
        "SELECT * FROM gst_rule_versions ORDER BY released_at DESC"
    )
    
    return [
        VersionResponse(
            id=row["id"],
            version=row["version"],
            released_at=row["released_at"],
            changelog=row["changelog"],
            rules_count=row["rules_count"],
        )
        for row in rows
    ]


@router.get("/versions/latest", response_model=VersionResponse)
async def get_latest_version(pool: DatabasePool = Depends(get_db_pool)):
    """Get the latest rule version"""
    
    row = await pool.fetchrow(
        "SELECT * FROM gst_rule_versions ORDER BY released_at DESC LIMIT 1"
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="No versions found")
    
    return VersionResponse(
        id=row["id"],
        version=row["version"],
        released_at=row["released_at"],
        changelog=row["changelog"],
        rules_count=row["rules_count"],
    )


@router.get("/versions/{version}", response_model=VersionResponse)
async def get_version(version: str, pool: DatabasePool = Depends(get_db_pool)):
    """Get a specific version"""
    
    row = await pool.fetchrow(
        "SELECT * FROM gst_rule_versions WHERE version = $1",
        version
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return VersionResponse(
        id=row["id"],
        version=row["version"],
        released_at=row["released_at"],
        changelog=row["changelog"],
        rules_count=row["rules_count"],
    )

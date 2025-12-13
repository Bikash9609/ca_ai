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


@router.get("/versions/check-updates")
async def check_updates(
    current_version: Optional[str] = Query(None),
    pool: DatabasePool = Depends(get_db_pool)
):
    """Check if there are updates available"""
    
    latest = await pool.fetchrow(
        "SELECT * FROM gst_rule_versions ORDER BY released_at DESC LIMIT 1"
    )
    
    if not latest:
        return {
            "has_update": False,
            "current_version": current_version,
            "latest_version": None
        }
    
    latest_version = latest["version"]
    has_update = current_version != latest_version if current_version else True
    
    return {
        "has_update": has_update,
        "current_version": current_version,
        "latest_version": latest_version,
        "latest_released_at": latest["released_at"].isoformat() if latest["released_at"] else None,
        "changelog": latest["changelog"],
        "rules_count": latest["rules_count"]
    }


@router.get("/versions/{version}/rules")
async def get_rules_for_version(
    version: str,
    pool: DatabasePool = Depends(get_db_pool)
):
    """Get all rules for a specific version"""
    from server.api.rules import RuleResponse
    
    rows = await pool.fetch(
        "SELECT * FROM gst_rules WHERE version = $1 AND is_active = TRUE ORDER BY rule_id",
        version
    )
    
    return [
        RuleResponse(
            id=row["id"],
            rule_id=row["rule_id"],
            name=row["name"],
            rule_text=row["rule_text"],
            citation=row["citation"],
            circular_number=row["circular_number"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
            category=row["category"],
            version=row["version"],
            is_active=row["is_active"],
        )
        for row in rows
    ]

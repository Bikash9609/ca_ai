"""
Privacy and audit logging API routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from pathlib import Path
from core.privacy import AuditLogger, get_workspace_size
from core.workspace import WorkspaceManager, get_default_workspace_path

router = APIRouter()


class PrivacyStatsResponse(BaseModel):
    total_queries: int
    total_data_shared_bytes: int
    recent_interactions: List[Dict[str, Any]]


class WorkspaceInfoResponse(BaseModel):
    path: str
    size_bytes: int
    file_count: int


# Global audit logger (will be initialized per client)
def get_audit_logger(client_id: str) -> AuditLogger:
    """Get audit logger for a client"""
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    audit_dir = workspace_manager.get_client_audit_path(client_id)
    return AuditLogger(audit_dir)


@router.get("/privacy/stats/{client_id}", response_model=PrivacyStatsResponse)
async def get_privacy_stats(client_id: str):
    """Get privacy statistics for a client"""
    try:
        logger = get_audit_logger(client_id)
        stats = logger.get_privacy_stats()
        return PrivacyStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get privacy stats: {str(e)}")


@router.get("/privacy/logs/{client_id}")
async def get_audit_logs(client_id: str, limit: int = 100):
    """Get audit logs for a client"""
    try:
        logger = get_audit_logger(client_id)
        logs = logger.get_recent_logs(limit=limit)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit logs: {str(e)}")


@router.get("/workspace/info", response_model=WorkspaceInfoResponse)
async def get_workspace_info():
    """Get workspace information"""
    workspace_path = get_default_workspace_path()
    
    if not workspace_path.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    size_bytes = get_workspace_size(workspace_path)
    
    # Count files
    file_count = sum(1 for _ in workspace_path.rglob("*") if _.is_file())
    
    return WorkspaceInfoResponse(
        path=str(workspace_path),
        size_bytes=size_bytes,
        file_count=file_count,
    )

"""
Privacy and audit logging API routes
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
from core.privacy import AuditLogger, get_workspace_size
from core.workspace import WorkspaceManager, get_default_workspace_path

router = APIRouter()


class PrivacyStatsResponse(BaseModel):
    total_queries: int
    total_data_shared_bytes: int
    recent_interactions: List[Dict[str, Any]]


class UsageStatisticsResponse(BaseModel):
    total_tool_calls: int
    tool_usage: Dict[str, int]
    data_shared_by_tool: Dict[str, int]
    average_result_size: float
    peak_usage_day: Optional[str]
    usage_by_hour: Dict[str, int]
    total_data_shared_bytes: int


class SecurityMonitoringResponse(BaseModel):
    total_violations: int
    violations_by_tool: Dict[str, int]
    violations_by_reason: Dict[str, int]
    recent_violations: List[Dict[str, Any]]
    suspicious_activity: bool


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


@router.get("/privacy/usage/{client_id}", response_model=UsageStatisticsResponse)
async def get_usage_statistics(client_id: str, days: int = Query(30, ge=1, le=365)):
    """Get detailed usage statistics"""
    try:
        logger = get_audit_logger(client_id)
        stats = logger.get_usage_statistics(days=days)
        return UsageStatisticsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get usage statistics: {str(e)}")


@router.get("/privacy/security/{client_id}", response_model=SecurityMonitoringResponse)
async def get_security_monitoring(client_id: str, days: int = Query(7, ge=1, le=30)):
    """Get security monitoring statistics"""
    try:
        logger = get_audit_logger(client_id)
        monitoring = logger.get_security_monitoring(days=days)
        return SecurityMonitoringResponse(**monitoring)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get security monitoring: {str(e)}")


@router.get("/privacy/logs/{client_id}/all")
async def get_all_logs(client_id: str):
    """Get all audit logs for export"""
    try:
        logger = get_audit_logger(client_id)
        logs = logger.get_all_logs()
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get all logs: {str(e)}")


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

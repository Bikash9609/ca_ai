"""
Privacy utilities and audit logging
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, List
from collections import defaultdict


class AuditLogger:
    """Immutable audit log for privacy tracking"""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "audit_log.jsonl"
    
    def log_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result_size: int,
        user_id: Optional[str] = None
    ) -> None:
        """Log a tool call to the audit log"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "params": self._sanitize_params(params),
            "result_size_bytes": result_size,
            "user_id": user_id,
        }
        
        # Append to JSONL file (immutable, append-only)
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize parameters for logging (remove sensitive data)"""
        sanitized = {}
        sensitive_keys = ["password", "api_key", "token", "secret"]
        
        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 100:
                sanitized[key] = value[:100] + "..."
            else:
                sanitized[key] = value
        
        return sanitized
    
    def get_recent_logs(self, limit: int = 100) -> list[Dict[str, Any]]:
        """Get recent log entries"""
        if not self.log_file.exists():
            return []
        
        logs = []
        with open(self.log_file, "r") as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    logs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        return logs
    
    def get_privacy_stats(self) -> Dict[str, Any]:
        """Get privacy statistics for dashboard"""
        if not self.log_file.exists():
            return {
                "total_queries": 0,
                "total_data_shared_bytes": 0,
                "recent_interactions": [],
            }
        
        total_queries = 0
        total_bytes = 0
        recent = []
        
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    total_queries += 1
                    total_bytes += entry.get("result_size_bytes", 0)
                    recent.append(entry)
                except json.JSONDecodeError:
                    continue
        
        return {
            "total_queries": total_queries,
            "total_data_shared_bytes": total_bytes,
            "recent_interactions": recent[-10:],  # Last 10 interactions
        }
    
    def rotate_log(self, max_size_mb: int = 100) -> None:
        """Rotate log file if it exceeds max size"""
        if not self.log_file.exists():
            return
        
        size_mb = self.log_file.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            # Archive old log
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_file = self.log_dir / f"audit_log_{timestamp}.jsonl"
            self.log_file.rename(archive_file)
            # Create new log file
            self.log_file.touch()
    
    def log_violation(
        self,
        tool_name: str,
        params: Dict[str, Any],
        reason: str,
        user_id: Optional[str] = None
    ) -> None:
        """Log a security violation (blocked tool call)"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "violation": True,
            "tool_name": tool_name,
            "params": self._sanitize_params(params),
            "reason": reason,
            "user_id": user_id,
        }
        
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def get_usage_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get detailed usage statistics"""
        if not self.log_file.exists():
            return {
                "total_tool_calls": 0,
                "tool_usage": {},
                "data_shared_by_tool": {},
                "average_result_size": 0,
                "peak_usage_day": None,
                "usage_by_hour": {},
            }
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        tool_usage = defaultdict(int)
        data_by_tool = defaultdict(int)
        hourly_usage = defaultdict(int)
        daily_usage = defaultdict(int)
        total_calls = 0
        total_bytes = 0
        
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("violation"):
                        continue
                    
                    timestamp_str = entry.get("timestamp", "")
                    if timestamp_str:
                        entry_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if entry_time.replace(tzinfo=None) < cutoff_date:
                            continue
                    
                    tool_name = entry.get("tool_name", "unknown")
                    tool_usage[tool_name] += 1
                    
                    result_size = entry.get("result_size_bytes", 0)
                    data_by_tool[tool_name] += result_size
                    total_bytes += result_size
                    total_calls += 1
                    
                    if timestamp_str:
                        entry_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        hourly_usage[entry_time.hour] += 1
                        day_key = entry_time.strftime("%Y-%m-%d")
                        daily_usage[day_key] += 1
                except (json.JSONDecodeError, ValueError):
                    continue
        
        peak_day = max(daily_usage.items(), key=lambda x: x[1])[0] if daily_usage else None
        
        return {
            "total_tool_calls": total_calls,
            "tool_usage": dict(tool_usage),
            "data_shared_by_tool": dict(data_by_tool),
            "average_result_size": total_bytes / total_calls if total_calls > 0 else 0,
            "peak_usage_day": peak_day,
            "usage_by_hour": dict(hourly_usage),
            "total_data_shared_bytes": total_bytes,
        }
    
    def get_security_monitoring(self, days: int = 7) -> Dict[str, Any]:
        """Get security monitoring statistics"""
        if not self.log_file.exists():
            return {
                "total_violations": 0,
                "violations_by_tool": {},
                "violations_by_reason": {},
                "recent_violations": [],
                "suspicious_activity": False,
            }
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        violations_by_tool = defaultdict(int)
        violations_by_reason = defaultdict(int)
        recent_violations = []
        total_violations = 0
        
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if not entry.get("violation"):
                        continue
                    
                    timestamp_str = entry.get("timestamp", "")
                    if timestamp_str:
                        entry_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if entry_time.replace(tzinfo=None) < cutoff_date:
                            continue
                    
                    total_violations += 1
                    tool_name = entry.get("tool_name", "unknown")
                    reason = entry.get("reason", "unknown")
                    
                    violations_by_tool[tool_name] += 1
                    violations_by_reason[reason] += 1
                    
                    recent_violations.append({
                        "timestamp": entry.get("timestamp"),
                        "tool_name": tool_name,
                        "reason": reason,
                    })
                except (json.JSONDecodeError, ValueError):
                    continue
        
        # Flag suspicious activity (more than 10 violations in a day)
        suspicious = total_violations > 10
        
        return {
            "total_violations": total_violations,
            "violations_by_tool": dict(violations_by_tool),
            "violations_by_reason": dict(violations_by_reason),
            "recent_violations": recent_violations[-20:],  # Last 20 violations
            "suspicious_activity": suspicious,
        }
    
    def get_all_logs(self) -> List[Dict[str, Any]]:
        """Get all log entries (for analysis)"""
        if not self.log_file.exists():
            return []
        
        logs = []
        with open(self.log_file, "r") as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        return logs


def get_workspace_size(workspace_path: Path) -> int:
    """Calculate total size of workspace in bytes"""
    total = 0
    for path in workspace_path.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total

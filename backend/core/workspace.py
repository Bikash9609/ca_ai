"""
Workspace management - directory structure and client management
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages workspace directory structure and clients"""
    
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.config_dir = workspace_path / "config"
        self.clients_dir = workspace_path / "clients"
        self._ensure_structure()
    
    def _ensure_structure(self) -> None:
        """Ensure workspace directory structure exists"""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.clients_dir.mkdir(parents=True, exist_ok=True)
    
    def create_client(
        self,
        name: str,
        gstin: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new client workspace"""
        # Generate client ID from name
        client_id = self._generate_client_id(name)
        client_dir = self.clients_dir / client_id
        
        if client_dir.exists():
            raise ValueError(f"Client with ID {client_id} already exists")
        
        client_dir.mkdir(parents=True, exist_ok=True)
        
        # Create client metadata
        client_metadata = {
            "id": client_id,
            "name": name,
            "gstin": gstin,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        
        metadata_file = client_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(client_metadata, f, indent=2)
        
        # Create client directory structure
        (client_dir / "documents").mkdir(exist_ok=True)
        (client_dir / "database").mkdir(exist_ok=True)
        (client_dir / "audit").mkdir(exist_ok=True)
        
        logger.info(f"Created client workspace: {client_id}")
        return client_id
    
    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client metadata"""
        client_dir = self.clients_dir / client_id
        metadata_file = client_dir / "metadata.json"
        
        if not metadata_file.exists():
            return None
        
        with open(metadata_file, "r") as f:
            return json.load(f)
    
    def list_clients(self) -> List[Dict[str, Any]]:
        """List all clients"""
        clients = []
        
        for client_dir in self.clients_dir.iterdir():
            if client_dir.is_dir():
                metadata_file = client_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, "r") as f:
                        clients.append(json.load(f))
        
        return sorted(clients, key=lambda x: x.get("createdAt", ""), reverse=True)
    
    def update_client(
        self,
        client_id: str,
        name: Optional[str] = None,
        gstin: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update client metadata"""
        client = self.get_client(client_id)
        if not client:
            return False
        
        if name:
            client["name"] = name
        if gstin is not None:
            client["gstin"] = gstin
        if metadata:
            client["metadata"].update(metadata)
        
        client["updatedAt"] = datetime.utcnow().isoformat()
        
        client_dir = self.clients_dir / client_id
        metadata_file = client_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(client, f, indent=2)
        
        return True
    
    def delete_client(self, client_id: str) -> bool:
        """Delete a client workspace"""
        client_dir = self.clients_dir / client_id
        if not client_dir.exists():
            return False
        
        # Remove directory and all contents
        import shutil
        shutil.rmtree(client_dir)
        logger.info(f"Deleted client workspace: {client_id}")
        return True
    
    def get_client_database_path(self, client_id: str) -> Path:
        """Get path to client's SQLite database"""
        return self.clients_dir / client_id / "database" / "index.db"
    
    def get_client_audit_path(self, client_id: str) -> Path:
        """Get path to client's audit log directory"""
        return self.clients_dir / client_id / "audit"
    
    def validate_workspace(self) -> tuple[bool, Optional[str]]:
        """Validate workspace structure"""
        if not self.workspace_path.exists():
            return False, "Workspace path does not exist"
        
        if not self.config_dir.exists():
            return False, "Config directory missing"
        
        if not self.clients_dir.exists():
            return False, "Clients directory missing"
        
        return True, None
    
    def _generate_client_id(self, name: str) -> str:
        """Generate a client ID from name"""
        # Simple slug generation
        import re
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower())
        slug = re.sub(r'_+', '_', slug).strip('_')
        
        # Add timestamp to ensure uniqueness
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        return f"{slug}_{timestamp}"


def get_default_workspace_path() -> Path:
    """Get default workspace path"""
    # Check for environment variable first
    env_path = os.getenv("CA_AI_WORKSPACE_PATH")
    if env_path:
        return Path(env_path)
    
    # Default to home directory
    home = Path.home()
    return home / "ca-ai-workspaces"

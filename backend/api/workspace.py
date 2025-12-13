"""
Workspace management API routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
from core.workspace import WorkspaceManager, get_default_workspace_path

router = APIRouter()


class CreateClientRequest(BaseModel):
    name: str
    gstin: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateClientRequest(BaseModel):
    name: Optional[str] = None
    gstin: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ClientResponse(BaseModel):
    id: str
    name: str
    gstin: Optional[str]
    createdAt: str
    updatedAt: str
    metadata: Dict[str, Any]


class WorkspaceResponse(BaseModel):
    path: str
    clients: List[ClientResponse]
    createdAt: str


# Global workspace manager (will be initialized on startup)
workspace_manager: Optional[WorkspaceManager] = None


def init_workspace_manager(workspace_path: Optional[Path] = None) -> None:
    """Initialize workspace manager"""
    global workspace_manager
    if workspace_path is None:
        workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)


@router.get("/workspace", response_model=WorkspaceResponse)
async def get_workspace():
    """Get workspace information"""
    if workspace_manager is None:
        init_workspace_manager()
    
    clients_data = workspace_manager.list_clients()
    clients = [
        ClientResponse(
            id=c["id"],
            name=c["name"],
            gstin=c.get("gstin"),
            createdAt=c["createdAt"],
            updatedAt=c["updatedAt"],
            metadata=c.get("metadata", {}),
        )
        for c in clients_data
    ]
    
    return WorkspaceResponse(
        path=str(workspace_manager.workspace_path),
        clients=clients,
        createdAt=datetime.utcnow().isoformat(),
    )


@router.post("/workspace/clients", response_model=ClientResponse)
async def create_client(request: CreateClientRequest):
    """Create a new client"""
    if workspace_manager is None:
        init_workspace_manager()
    
    try:
        client_id = workspace_manager.create_client(
            name=request.name,
            gstin=request.gstin,
            metadata=request.metadata,
        )
        client = workspace_manager.get_client(client_id)
        
        if not client:
            raise HTTPException(status_code=500, detail="Failed to retrieve created client")
        
        return ClientResponse(
            id=client["id"],
            name=client["name"],
            gstin=client.get("gstin"),
            createdAt=client["createdAt"],
            updatedAt=client["updatedAt"],
            metadata=client.get("metadata", {}),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workspace/clients", response_model=List[ClientResponse])
async def list_clients():
    """List all clients"""
    if workspace_manager is None:
        init_workspace_manager()
    
    clients_data = workspace_manager.list_clients()
    return [
        ClientResponse(
            id=c["id"],
            name=c["name"],
            gstin=c.get("gstin"),
            createdAt=c["createdAt"],
            updatedAt=c["updatedAt"],
            metadata=c.get("metadata", {}),
        )
        for c in clients_data
    ]


@router.get("/workspace/clients/{client_id}", response_model=ClientResponse)
async def get_client(client_id: str):
    """Get a specific client"""
    if workspace_manager is None:
        init_workspace_manager()
    
    client = workspace_manager.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return ClientResponse(
        id=client["id"],
        name=client["name"],
        gstin=client.get("gstin"),
        createdAt=client["createdAt"],
        updatedAt=client["updatedAt"],
        metadata=client.get("metadata", {}),
    )


@router.put("/workspace/clients/{client_id}", response_model=ClientResponse)
async def update_client(client_id: str, request: UpdateClientRequest):
    """Update a client"""
    if workspace_manager is None:
        init_workspace_manager()
    
    success = workspace_manager.update_client(
        client_id=client_id,
        name=request.name,
        gstin=request.gstin,
        metadata=request.metadata,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client = workspace_manager.get_client(client_id)
    return ClientResponse(
        id=client["id"],
        name=client["name"],
        gstin=client.get("gstin"),
        createdAt=client["createdAt"],
        updatedAt=client["updatedAt"],
        metadata=client.get("metadata", {}),
    )


@router.delete("/workspace/clients/{client_id}")
async def delete_client(client_id: str):
    """Delete a client"""
    if workspace_manager is None:
        init_workspace_manager()
    
    success = workspace_manager.delete_client(client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return {"message": "Client deleted successfully"}

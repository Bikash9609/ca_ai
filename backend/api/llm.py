"""
LLM API routes
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from services.llm import LLMService, LLMProvider
from core.firewall import ContextFirewall
from core.tools import ToolExecutor
from core.privacy import AuditLogger
from core.workspace import WorkspaceManager, get_default_workspace_path
from database.connection import DatabaseManager

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    client_id: str
    provider: Optional[str] = "claude"  # "claude", "ollama", "gemini", "groq", "openrouter"
    api_key: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    tool_calls: list = []


# Global service instances (would be better with dependency injection)
_llm_services: dict = {}


def get_llm_service(
    client_id: str,
    provider: str = "claude",
    api_key: Optional[str] = None
) -> LLMService:
    """Get or create LLM service for a client"""
    cache_key = f"{client_id}_{provider}"
    
    if cache_key in _llm_services:
        return _llm_services[cache_key]
    
    # Initialize components
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    
    # Database manager
    db_path = workspace_manager.get_client_database_path(client_id)
    db_manager = DatabaseManager(str(db_path))
    
    # Tool executor
    tool_executor = ToolExecutor(
        db_manager=db_manager,
        client_id=client_id
    )
    
    # Firewall
    firewall = ContextFirewall()
    
    # Audit logger
    audit_dir = workspace_manager.get_client_audit_path(client_id)
    audit_logger = AuditLogger(audit_dir)
    firewall.audit_logger = audit_logger
    firewall.user_id = client_id
    
    # LLM provider
    provider_map = {
        "claude": LLMProvider.CLAUDE,
        "ollama": LLMProvider.OLLAMA,
        "gemini": LLMProvider.GEMINI,
        "groq": LLMProvider.GROQ,
        "openrouter": LLMProvider.OPENROUTER,
    }
    llm_provider = provider_map.get(provider, LLMProvider.CLAUDE)
    
    # Create service
    service = LLMService(
        firewall=firewall,
        tool_executor=tool_executor,
        audit_logger=audit_logger,
        api_key=api_key,
        provider=llm_provider
    )
    
    _llm_services[cache_key] = service
    return service


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response with tool calling"""
    try:
        service = get_llm_service(
            client_id=request.client_id,
            provider=request.provider,
            api_key=request.api_key
        )
        
        async def generate():
            async for chunk in service.process_query(request.query):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint (non-streaming)"""
    try:
        service = get_llm_service(
            client_id=request.client_id,
            provider=request.provider,
            api_key=request.api_key
        )
        
        response_text = ""
        tool_calls = []
        
        async for chunk in service.process_query(request.query):
            if chunk["type"] == "text":
                response_text += chunk["content"]
            elif chunk["type"] == "tool_call":
                tool_calls.append(chunk["content"])
            elif chunk["type"] == "error":
                raise HTTPException(status_code=500, detail=chunk["content"])
        
        return ChatResponse(
            response=response_text,
            tool_calls=tool_calls
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.post("/chat/history/clear")
async def clear_history(client_id: str, provider: str = "claude"):
    """Clear conversation history"""
    try:
        service = get_llm_service(client_id=client_id, provider=provider)
        service.clear_history()
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")


@router.get("/chat/history")
async def get_history(client_id: str, provider: str = "claude"):
    """Get conversation history"""
    try:
        service = get_llm_service(client_id=client_id, provider=provider)
        history = service.get_history()
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting history: {str(e)}")

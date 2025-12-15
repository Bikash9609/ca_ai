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
        provider=llm_provider,
        db_manager=db_manager,
        client_id=client_id
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


# Conversation management endpoints
class ConversationCreate(BaseModel):
    client_id: str
    title: Optional[str] = None
    provider: Optional[str] = "claude"


class ConversationUpdate(BaseModel):
    title: Optional[str] = None


@router.get("/chat/conversations")
async def list_conversations(client_id: str, limit: int = 50, offset: int = 0):
    """List conversations for a client"""
    try:
        workspace_path = get_default_workspace_path()
        workspace_manager = WorkspaceManager(workspace_path)
        db_path = workspace_manager.get_client_database_path(client_id)
        db_manager = DatabaseManager(str(db_path))
        
        query = """
            SELECT id, title, provider, created_at, updated_at, metadata
            FROM conversations
            WHERE client_id = ?
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        
        rows = await db_manager.fetchall(query, (client_id, limit, offset))
        
        conversations = []
        for row in rows:
            conversations.append({
                "id": row[0],
                "title": row[1] or "New Conversation",
                "provider": row[2] or "claude",
                "created_at": row[3],
                "updated_at": row[4],
                "metadata": json.loads(row[5]) if row[5] else {}
            })
        
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing conversations: {str(e)}")


@router.post("/chat/conversations")
async def create_conversation(conv: ConversationCreate):
    """Create a new conversation"""
    try:
        import uuid
        from datetime import datetime
        
        workspace_path = get_default_workspace_path()
        workspace_manager = WorkspaceManager(workspace_path)
        db_path = workspace_manager.get_client_database_path(conv.client_id)
        db_manager = DatabaseManager(str(db_path))
        
        conv_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        title = conv.title or "New Conversation"
        
        query = """
            INSERT INTO conversations (id, client_id, title, provider, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        await db_manager.execute(
            query,
            (conv_id, conv.client_id, title, conv.provider, now, now, json.dumps({}))
        )
        
        return {
            "id": conv_id,
            "title": title,
            "provider": conv.provider,
            "created_at": now,
            "updated_at": now,
            "metadata": {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating conversation: {str(e)}")


@router.get("/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, client_id: str):
    """Get a conversation with its messages"""
    try:
        workspace_path = get_default_workspace_path()
        workspace_manager = WorkspaceManager(workspace_path)
        db_path = workspace_manager.get_client_database_path(client_id)
        db_manager = DatabaseManager(str(db_path))
        
        # Get conversation
        conv_query = """
            SELECT id, title, provider, created_at, updated_at, metadata
            FROM conversations
            WHERE id = ? AND client_id = ?
        """
        conv_row = await db_manager.fetchone(conv_query, (conversation_id, client_id))
        
        if not conv_row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages
        msg_query = """
            SELECT id, role, content, tool_calls, created_at
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
        """
        msg_rows = await db_manager.fetchall(msg_query, (conversation_id,))
        
        messages = []
        for row in msg_rows:
            messages.append({
                "id": row[0],
                "role": row[1],
                "content": row[2],
                "tool_calls": json.loads(row[3]) if row[3] else [],
                "created_at": row[4]
            })
        
        return {
            "id": conv_row[0],
            "title": conv_row[1] or "New Conversation",
            "provider": conv_row[2] or "claude",
            "created_at": conv_row[3],
            "updated_at": conv_row[4],
            "metadata": json.loads(conv_row[5]) if conv_row[5] else {},
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting conversation: {str(e)}")


@router.put("/chat/conversations/{conversation_id}/title")
async def update_conversation_title(conversation_id: str, client_id: str, update: ConversationUpdate):
    """Update conversation title"""
    try:
        from datetime import datetime
        
        workspace_path = get_default_workspace_path()
        workspace_manager = WorkspaceManager(workspace_path)
        db_path = workspace_manager.get_client_database_path(client_id)
        db_manager = DatabaseManager(str(db_path))
        
        if not update.title:
            raise HTTPException(status_code=400, detail="Title is required")
        
        now = datetime.utcnow().isoformat()
        
        query = """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ? AND client_id = ?
        """
        
        await db_manager.execute(query, (update.title, now, conversation_id, client_id))
        
        return {"status": "updated", "title": update.title}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating conversation: {str(e)}")


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, client_id: str):
    """Delete a conversation"""
    try:
        workspace_path = get_default_workspace_path()
        workspace_manager = WorkspaceManager(workspace_path)
        db_path = workspace_manager.get_client_database_path(client_id)
        db_manager = DatabaseManager(str(db_path))
        
        query = "DELETE FROM conversations WHERE id = ? AND client_id = ?"
        await db_manager.execute(query, (conversation_id, client_id))
        
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting conversation: {str(e)}")

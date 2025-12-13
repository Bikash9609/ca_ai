"""
API routes for the backend
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from api.workspace import router as workspace_router
from api.privacy import router as privacy_router

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(status="healthy", service="CA AI Backend")

# Include workspace routes
router.include_router(workspace_router)
# Include privacy routes
router.include_router(privacy_router)

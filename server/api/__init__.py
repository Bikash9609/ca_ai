"""API routes module"""

from .rules import router as rules_router
from .versions import router as versions_router

__all__ = ["rules_router", "versions_router"]

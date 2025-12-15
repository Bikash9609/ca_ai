"""
Caching Layer - Cache embeddings, context bundles, and LLM responses
"""

import hashlib
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Cache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, ttl: int = 3600):
        """
        Initialize cache
        
        Args:
            ttl: Time to live in seconds (default: 1 hour)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items()) if kwargs else []
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() > entry["expires_at"]:
            del self.cache[key]
            return None
        
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache"""
        ttl = ttl or self.ttl
        self.cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl
        }
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self.cache.clear()
    
    def size(self) -> int:
        """Get cache size"""
        return len(self.cache)


class EmbeddingCache:
    """Cache for query embeddings"""
    
    def __init__(self, cache: Cache):
        """
        Initialize embedding cache
        
        Args:
            cache: Cache instance
        """
        self.cache = cache
        self.prefix = "embedding"
    
    def get(self, text: str) -> Optional[Any]:
        """Get cached embedding"""
        key = self.cache._make_key(self.prefix, text)
        return self.cache.get(key)
    
    def set(self, text: str, embedding: Any) -> None:
        """Cache embedding"""
        key = self.cache._make_key(self.prefix, text)
        self.cache.set(key, embedding, ttl=86400)  # 24 hours for embeddings


class ContextCache:
    """Cache for context bundles"""
    
    def __init__(self, cache: Cache):
        """
        Initialize context cache
        
        Args:
            cache: Cache instance
        """
        self.cache = cache
        self.prefix = "context"
    
    def get(self, query: str, filters: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
        """Get cached context bundle"""
        key = self.cache._make_key(self.prefix, query, filters or {})
        return self.cache.get(key)
    
    def set(self, query: str, context: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> None:
        """Cache context bundle"""
        key = self.cache._make_key(self.prefix, query, filters or {})
        self.cache.set(key, context, ttl=1800)  # 30 minutes for context


class ResponseCache:
    """Cache for LLM responses"""
    
    def __init__(self, cache: Cache):
        """
        Initialize response cache
        
        Args:
            cache: Cache instance
        """
        self.cache = cache
        self.prefix = "response"
    
    def get(self, query: str, context_hash: Optional[str] = None) -> Optional[str]:
        """Get cached response"""
        key = self.cache._make_key(self.prefix, query, context_hash or "")
        return self.cache.get(key)
    
    def set(self, query: str, response: str, context_hash: Optional[str] = None) -> None:
        """Cache response"""
        key = self.cache._make_key(self.prefix, query, context_hash or "")
        self.cache.set(key, response, ttl=3600)  # 1 hour for responses


# Global cache instance
_global_cache: Optional[Cache] = None


def get_cache() -> Cache:
    """Get global cache instance"""
    global _global_cache
    if _global_cache is None:
        import os
        ttl = int(os.getenv("CACHE_TTL", "3600"))
        _global_cache = Cache(ttl=ttl)
    return _global_cache


def get_embedding_cache() -> EmbeddingCache:
    """Get embedding cache"""
    return EmbeddingCache(get_cache())


def get_context_cache() -> ContextCache:
    """Get context cache"""
    return ContextCache(get_cache())


def get_response_cache() -> ResponseCache:
    """Get response cache"""
    return ResponseCache(get_cache())

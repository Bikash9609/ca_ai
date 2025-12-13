"""
Client sync service for downloading and caching rules
"""

import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import httpx
from server.database.connection import DatabasePool

logger = logging.getLogger(__name__)


class RulesSyncService:
    """Service to sync rules from server to client"""
    
    def __init__(self, server_url: str, cache_dir: Path):
        """
        Initialize sync service
        
        Args:
            server_url: Base URL of the rules server
            cache_dir: Directory to cache rules locally
        """
        self.server_url = server_url.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def check_for_updates(self, current_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Check if there are updates available
        
        Args:
            current_version: Current version string
            
        Returns:
            Dictionary with update information
        """
        try:
            params = {}
            if current_version:
                params["current_version"] = current_version
            
            response = await self.client.get(
                f"{self.server_url}/api/v1/versions/check-updates",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            raise
    
    async def download_rules(self, version: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Download rules from server
        
        Args:
            version: Specific version to download (None for latest)
            
        Returns:
            List of rule dictionaries
        """
        try:
            if version:
                url = f"{self.server_url}/api/v1/versions/{version}/rules"
            else:
                # Get latest version first
                latest_response = await self.client.get(f"{self.server_url}/api/v1/versions/latest")
                latest_response.raise_for_status()
                latest_data = latest_response.json()
                version = latest_data["version"]
                url = f"{self.server_url}/api/v1/versions/{version}/rules"
            
            response = await self.client.get(url)
            response.raise_for_status()
            rules = response.json()
            
            # Cache rules
            await self._cache_rules(version, rules)
            
            return rules
        except Exception as e:
            logger.error(f"Error downloading rules: {e}")
            raise
    
    async def _cache_rules(self, version: str, rules: List[Dict[str, Any]]) -> None:
        """
        Cache rules to local file
        
        Args:
            version: Version string
            rules: List of rule dictionaries
        """
        cache_file = self.cache_dir / f"rules_{version}.json"
        
        cache_data = {
            "version": version,
            "cached_at": datetime.utcnow().isoformat(),
            "rules_count": len(rules),
            "rules": rules
        }
        
        try:
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2, default=str)
            logger.info(f"Cached {len(rules)} rules for version {version}")
        except Exception as e:
            logger.error(f"Error caching rules: {e}")
            raise
    
    async def load_cached_rules(self, version: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Load cached rules from local file
        
        Args:
            version: Specific version to load (None for latest cached)
            
        Returns:
            List of rule dictionaries or None if not found
        """
        if version:
            cache_file = self.cache_dir / f"rules_{version}.json"
        else:
            # Find latest cached version
            cache_files = sorted(self.cache_dir.glob("rules_*.json"), reverse=True)
            if not cache_files:
                return None
            cache_file = cache_files[0]
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)
            logger.info(f"Loaded {cache_data['rules_count']} cached rules for version {cache_data['version']}")
            return cache_data.get("rules", [])
        except Exception as e:
            logger.error(f"Error loading cached rules: {e}")
            return None
    
    def get_cached_versions(self) -> List[str]:
        """
        Get list of cached versions
        
        Returns:
            List of version strings
        """
        cache_files = self.cache_dir.glob("rules_*.json")
        versions = []
        
        for cache_file in cache_files:
            try:
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)
                    versions.append(cache_data["version"])
            except Exception:
                continue
        
        return sorted(versions, reverse=True)
    
    async def sync_rules(self, current_version: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        Sync rules from server (check for updates and download if needed)
        
        Args:
            current_version: Current version string
            force: Force download even if version matches
            
        Returns:
            Dictionary with sync results
        """
        try:
            # Check for updates
            update_info = await self.check_for_updates(current_version)
            
            if not update_info["has_update"] and not force:
                # Try to load from cache
                cached_rules = await self.load_cached_rules(current_version)
                if cached_rules:
                    return {
                        "updated": False,
                        "version": current_version,
                        "rules_count": len(cached_rules),
                        "source": "cache"
                    }
                else:
                    # No cache, download anyway
                    rules = await self.download_rules()
                    return {
                        "updated": True,
                        "version": update_info["latest_version"],
                        "rules_count": len(rules),
                        "source": "server"
                    }
            
            # Download latest rules
            rules = await self.download_rules()
            
            return {
                "updated": True,
                "version": update_info["latest_version"],
                "rules_count": len(rules),
                "source": "server"
            }
        except Exception as e:
            logger.error(f"Error syncing rules: {e}")
            # Try to load from cache as fallback
            cached_rules = await self.load_cached_rules()
            if cached_rules:
                logger.info("Using cached rules as fallback")
                return {
                    "updated": False,
                    "version": "cached",
                    "rules_count": len(cached_rules),
                    "source": "cache_fallback",
                    "error": str(e)
                }
            raise
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

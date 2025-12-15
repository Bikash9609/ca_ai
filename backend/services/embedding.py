"""
Embedding Generation - Sentence transformers for document embeddings
"""

import numpy as np
from typing import List, Optional, Dict, Any
import logging
from pathlib import Path
import hashlib
import json
import os

try:
    from sentence_transformers import SentenceTransformer
    import huggingface_hub
except ImportError:
    SentenceTransformer = None
    huggingface_hub = None

logger = logging.getLogger(__name__)

# Import cache if available
try:
    from services.cache import get_embedding_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


class EmbeddingGenerator:
    """Generate embeddings using sentence-transformers"""
    
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384
    
    def __init__(self, model_name: Optional[str] = None, cache_dir: Optional[Path] = None):
        """
        Initialize embedding generator
        
        Args:
            model_name: Model name (default: all-MiniLM-L6-v2)
            cache_dir: Directory to cache models
        """
        if SentenceTransformer is None:
            raise ImportError("sentence-transformers is required. Install with: uv pip install sentence-transformers")
        
        self.model_name = model_name or self.DEFAULT_MODEL
        self.cache_dir = cache_dir
        
        # Configure Hugging Face Hub timeouts
        if huggingface_hub:
            os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
            os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT_STREAMING", "300")
        
        # Load model (will download and cache if needed)
        try:
            # Try offline mode first if model might be cached
            try:
                if cache_dir:
                    self.model = SentenceTransformer(self.model_name, cache_folder=str(cache_dir), local_files_only=True)
                else:
                    self.model = SentenceTransformer(self.model_name, local_files_only=True)
                logger.info(f"Loaded embedding model from cache: {self.model_name}")
            except Exception:
                # If offline fails, try online with longer timeout
                logger.info(f"Model not in cache, downloading: {self.model_name}")
                if cache_dir:
                    self.model = SentenceTransformer(self.model_name, cache_folder=str(cache_dir))
                else:
                    self.model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded embedding model: {self.model_name}")
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
            raise
    
    def generate(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text
            use_cache: Whether to use cache (default: True)
        
        Returns:
            Embedding vector as numpy array
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)
        
        # Check cache if enabled
        if use_cache and CACHE_AVAILABLE and os.getenv("ENABLE_CACHE", "true").lower() == "true":
            embedding_cache = get_embedding_cache()
            cached = embedding_cache.get(text)
            if cached is not None:
                return cached
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            embedding = embedding.astype(np.float32)
            
            # Cache if enabled
            if use_cache and CACHE_AVAILABLE and os.getenv("ENABLE_CACHE", "true").lower() == "true":
                embedding_cache = get_embedding_cache()
                embedding_cache.set(text, embedding)
            
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return zero vector on error
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)
    
    def generate_batch(self, texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts in batch
        
        Args:
            texts: List of input texts
            batch_size: Batch size for processing
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        print(f"[EMBEDDING] Generating embeddings for {len(texts)} texts (batch_size: {batch_size})")
        
        # Filter out empty texts
        valid_texts = [t if t and t.strip() else "" for t in texts]
        
        try:
            embeddings = self.model.encode(
                valid_texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            result = [emb.astype(np.float32) for emb in embeddings]
            print(f"[EMBEDDING] Generated {len(result)} embeddings, dimension: {self.EMBEDDING_DIM}")
            for i, emb in enumerate(result):
                print(f"[EMBEDDING] Vector {i}: shape={emb.shape}, sample (first 5 values)={emb[:5].tolist()}, norm={np.linalg.norm(emb):.4f}")
            return result
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            print(f"[EMBEDDING] Error generating embeddings: {e}")
            # Return zero vectors on error
            return [np.zeros(self.EMBEDDING_DIM, dtype=np.float32) for _ in texts]
    
    def get_embedding_dim(self) -> int:
        """Get embedding dimension"""
        return self.EMBEDDING_DIM
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "model_name": self.model_name,
            "embedding_dim": self.EMBEDDING_DIM,
            "max_seq_length": getattr(self.model, 'max_seq_length', None) if self.model else None
        }


class EmbeddingCache:
    """Cache embeddings to avoid recomputation"""
    
    def __init__(self, cache_dir: Path):
        """
        Initialize embedding cache
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path"""
        return self.cache_dir / f"{cache_key}.npy"
    
    def get(self, text: str) -> Optional[np.ndarray]:
        """
        Get cached embedding
        
        Args:
            text: Input text
        
        Returns:
            Cached embedding or None
        """
        cache_key = self._get_cache_key(text)
        cache_path = self._get_cache_path(cache_key)
        
        if cache_path.exists():
            try:
                return np.load(cache_path)
            except Exception as e:
                logger.debug(f"Error loading cached embedding: {e}")
                return None
        return None
    
    def set(self, text: str, embedding: np.ndarray) -> None:
        """
        Cache an embedding
        
        Args:
            text: Input text
            embedding: Embedding vector
        """
        cache_key = self._get_cache_key(text)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            np.save(cache_path, embedding)
        except Exception as e:
            logger.error(f"Error caching embedding: {e}")
    
    def clear(self) -> None:
        """Clear all cached embeddings"""
        try:
            for cache_file in self.cache_dir.glob("*.npy"):
                cache_file.unlink()
            logger.info("Cleared embedding cache")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_cache_size(self) -> int:
        """Get number of cached embeddings"""
        try:
            return len(list(self.cache_dir.glob("*.npy")))
        except Exception:
            return 0

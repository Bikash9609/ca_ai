"""
Search Implementation - Semantic, full-text, and hybrid search
"""

import numpy as np
from typing import List, Dict, Any, Optional
import logging
import json

from database.connection import DatabaseManager

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


class SemanticSearch:
    """Semantic search using vector similarity"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize semantic search
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
    
    def _blob_to_embedding(self, blob: bytes) -> np.ndarray:
        """Convert BLOB to numpy array"""
        return np.frombuffer(blob, dtype=np.float32)
    
    async def search(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using vector similarity
        
        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results
            threshold: Minimum similarity threshold
            filters: Optional filters (document_id, client_id, period, etc.)
        
        Returns:
            List of search results with similarity scores
        """
        # Build filter conditions
        filter_conditions = []
        filter_params = []
        
        if filters:
            if "document_id" in filters:
                filter_conditions.append("dc.document_id = ?")
                filter_params.append(filters["document_id"])
            
            if "client_id" in filters:
                # Join with documents table
                filter_conditions.append("d.client_id = ?")
                filter_params.append(filters["client_id"])
            
            if "period" in filters:
                filter_conditions.append("d.period = ?")
                filter_params.append(filters["period"])
            
            if "category" in filters:
                filter_conditions.append("d.category = ?")
                filter_params.append(filters["category"])
        
        filter_sql = ""
        if filter_conditions:
            filter_sql = "WHERE " + " AND ".join(filter_conditions)
        
        # Get all chunks with embeddings
        query = f"""
            SELECT 
                dc.id,
                dc.document_id,
                dc.chunk_index,
                dc.text,
                dc.embedding,
                dc.metadata,
                d.client_id,
                d.period,
                d.category,
                d.doc_type
            FROM document_chunks dc
            LEFT JOIN documents d ON dc.document_id = d.id
            {filter_sql}
        """
        
        rows = await self.db.fetchall(query, tuple(filter_params))
        
        # Calculate similarities
        results = []
        for row in rows:
            chunk_id = row[0]
            document_id = row[1]
            chunk_index = row[2]
            text = row[3]
            embedding_blob = row[4]
            metadata = json.loads(row[5]) if row[5] else None
            
            if not embedding_blob:
                continue
            
            # Calculate similarity
            chunk_embedding = self._blob_to_embedding(embedding_blob)
            similarity = cosine_similarity(query_embedding, chunk_embedding)
            
            if similarity >= threshold:
                results.append({
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "text": text,
                    "similarity": similarity,
                    "metadata": metadata,
                    "client_id": row[6],
                    "period": row[7],
                    "category": row[8],
                    "doc_type": row[9]
                })
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Return top results
        return results[:limit]


class FullTextSearch:
    """Full-text search using FTS5"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize full-text search
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using full-text search
        
        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional filters
        
        Returns:
            List of search results
        """
        # Build filter conditions
        filter_conditions = []
        filter_params = [query]  # FTS5 query parameter
        
        if filters:
            if "document_id" in filters:
                filter_conditions.append("dc.document_id = ?")
                filter_params.append(filters["document_id"])
            
            if "client_id" in filters:
                filter_conditions.append("d.client_id = ?")
                filter_params.append(filters["client_id"])
            
            if "period" in filters:
                filter_conditions.append("d.period = ?")
                filter_params.append(filters["period"])
        
        filter_sql = ""
        if filter_conditions:
            filter_sql = "AND " + " AND ".join(filter_conditions)
        
        # FTS5 search query
        search_query = f"""
            SELECT 
                dc.id,
                dc.document_id,
                dc.chunk_index,
                dc.text,
                dc.metadata,
                d.client_id,
                d.period,
                d.category,
                d.doc_type,
                bm25(document_fts) as rank
            FROM document_fts
            JOIN document_chunks dc ON document_fts.rowid = dc.rowid
            LEFT JOIN documents d ON dc.document_id = d.id
            WHERE document_fts MATCH ?
            {filter_sql}
            ORDER BY rank
            LIMIT ?
        """
        
        filter_params.append(limit)
        
        rows = await self.db.fetchall(search_query, tuple(filter_params))
        
        results = []
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "text": row[3],
                "metadata": json.loads(row[4]) if row[4] else None,
                "rank": row[9],
                "client_id": row[5],
                "period": row[6],
                "category": row[7],
                "doc_type": row[8]
            })
        
        return results


class HybridSearch:
    """Hybrid search combining semantic and full-text search"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """
        Initialize hybrid search
        
        Args:
            db_manager: Database manager
            semantic_weight: Weight for semantic search (0-1)
            keyword_weight: Weight for keyword search (0-1)
        """
        self.semantic_search = SemanticSearch(db_manager)
        self.fulltext_search = FullTextSearch(db_manager)
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        
        # Normalize weights
        total = semantic_weight + keyword_weight
        if total > 0:
            self.semantic_weight = semantic_weight / total
            self.keyword_weight = keyword_weight / total
    
    async def search(
        self,
        query: str,
        query_embedding: np.ndarray,
        limit: int = 10,
        semantic_threshold: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search
        
        Args:
            query: Text query for keyword search
            query_embedding: Embedding for semantic search
            limit: Maximum number of results
            semantic_threshold: Minimum similarity threshold
            filters: Optional filters
        
        Returns:
            Merged and ranked search results
        """
        # Perform both searches
        semantic_results = await self.semantic_search.search(
            query_embedding,
            limit=limit * 2,  # Get more results for merging
            threshold=semantic_threshold,
            filters=filters
        )
        
        keyword_results = await self.fulltext_search.search(
            query,
            limit=limit * 2,
            filters=filters
        )
        
        # Create result maps for merging
        semantic_map = {r["chunk_id"]: r for r in semantic_results}
        keyword_map = {r["chunk_id"]: r for r in keyword_results}
        
        # Normalize scores
        if semantic_results:
            max_semantic = max(r["similarity"] for r in semantic_results)
            min_semantic = min(r["similarity"] for r in semantic_results)
            semantic_range = max_semantic - min_semantic if max_semantic != min_semantic else 1.0
        else:
            semantic_range = 1.0
        
        if keyword_results:
            max_rank = max(r["rank"] for r in keyword_results)
            min_rank = min(r["rank"] for r in keyword_results)
            rank_range = max_rank - min_rank if max_rank != min_rank else 1.0
        else:
            rank_range = 1.0
        
        # Merge results
        merged_results = {}
        all_chunk_ids = set(semantic_map.keys()) | set(keyword_map.keys())
        
        for chunk_id in all_chunk_ids:
            semantic_score = 0.0
            keyword_score = 0.0
            
            if chunk_id in semantic_map:
                # Normalize similarity to 0-1
                similarity = semantic_map[chunk_id]["similarity"]
                semantic_score = (similarity - min_semantic) / semantic_range if semantic_range > 0 else 0.0
            
            if chunk_id in keyword_map:
                # Normalize rank (lower rank = better, so invert)
                rank = keyword_map[chunk_id]["rank"]
                keyword_score = 1.0 - ((rank - min_rank) / rank_range if rank_range > 0 else 0.0)
            
            # Combined score
            combined_score = (
                self.semantic_weight * semantic_score +
                self.keyword_weight * keyword_score
            )
            
            # Get result data (prefer semantic as it has more fields)
            result_data = semantic_map.get(chunk_id) or keyword_map[chunk_id]
            result_data = result_data.copy()
            result_data["combined_score"] = combined_score
            result_data["semantic_score"] = semantic_score
            result_data["keyword_score"] = keyword_score
            
            merged_results[chunk_id] = result_data
        
        # Sort by combined score
        sorted_results = sorted(
            merged_results.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        return sorted_results[:limit]

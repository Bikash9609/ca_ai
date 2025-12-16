"""
Search Implementation - Semantic, full-text, and hybrid search
"""

import numpy as np
from typing import List, Dict, Any, Optional
import logging
import json
import os
import re

from database.connection import DatabaseManager

logger = logging.getLogger(__name__)

# Import cache if available
try:
    from services.cache import get_context_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


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


class MultiPassRetriever:
    """Multi-pass context retrieval pipeline (Cursor-style)"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """
        Initialize multi-pass retriever
        
        Args:
            db_manager: Database manager
            semantic_weight: Weight for semantic search
            keyword_weight: Weight for keyword search
        """
        self.db = db_manager
        self.hybrid_search = HybridSearch(db_manager, semantic_weight, keyword_weight)
        self.semantic_search = SemanticSearch(db_manager)
    
    async def retrieve_context(
        self,
        query: str,
        query_embedding: np.ndarray,
        client_id: str,
        limit: int = 15,
        filters: Optional[Dict[str, Any]] = None,
        max_initial_results: int = 30,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Multi-pass retrieval: Vector search → Filtering → Expansion
        
        Args:
            query: User question
            query_embedding: Query embedding vector
            client_id: Client ID
            limit: Final number of chunks to return (5-15 recommended)
            filters: Optional filters
            max_initial_results: Maximum results from Pass A (before filtering)
            use_cache: Whether to use cache (default: True)
        
        Returns:
            Context bundle with 5-15 chunks
        """
        # Check cache if enabled
        if use_cache and CACHE_AVAILABLE and os.getenv("ENABLE_CACHE", "true").lower() == "true":
            context_cache = get_context_cache()
            cached = context_cache.get(query, filters)
            if cached is not None:
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return cached
        
        # Pass A: Vector search (semantic similarity)
        initial_results = await self._pass_a_vector_search(
            query, query_embedding, client_id, max_initial_results, filters
        )
        
        if not initial_results:
            return []
        
        # Pass B: Filtering
        filtered_results = await self._pass_b_filtering(
            initial_results, query, filters
        )
        
        if not filtered_results:
            return []
        
        # Pass C: Context expansion
        expanded_results = await self._pass_c_expansion(
            filtered_results, client_id, limit
        )
        
        final_results = expanded_results[:limit]
        
        # Cache results if enabled
        if use_cache and CACHE_AVAILABLE and os.getenv("ENABLE_CACHE", "true").lower() == "true":
            context_cache = get_context_cache()
            context_cache.set(query, final_results, filters)
        
        return final_results
    
    async def _pass_a_vector_search(
        self,
        query: str,
        query_embedding: np.ndarray,
        client_id: str,
        limit: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Pass A: Semantic similarity search"""
        search_filters = {"client_id": client_id}
        if filters:
            search_filters.update(filters)
        
        # Use hybrid search for better results
        results = await self.hybrid_search.search(
            query=query,
            query_embedding=query_embedding,
            limit=limit,
            semantic_threshold=0.3,  # Minimum similarity
            filters=search_filters
        )
        
        return results
    
    async def _pass_b_filtering(
        self,
        results: List[Dict[str, Any]],
        query: str,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Pass B: Filter out irrelevant chunks"""
        filtered = []
        
        # Extract query intent (simple keyword-based)
        query_lower = query.lower()
        is_payment_query = any(word in query_lower for word in ['payment', 'paid', 'pay', 'transaction', 'amount'])
        is_tds_query = any(word in query_lower for word in ['tds', 'tax', 'deduction'])
        is_invoice_query = any(word in query_lower for word in ['invoice', 'bill', 'receipt'])
        
        # Extract time hints from query
        time_hints = self._extract_time_hints(query)
        
        for result in results:
            # Filter by doc_type if specified
            if filters and "doc_type" in filters:
                if result.get("doc_type") != filters["doc_type"]:
                    continue
            
            # Filter by period if time hints in query
            if time_hints and result.get("period"):
                if not self._period_matches(result.get("period"), time_hints):
                    continue
            
            # Filter by chunk type for payment queries
            if is_payment_query:
                chunk_metadata = result.get("metadata", {})
                chunk_type = chunk_metadata.get("chunk_type", "")
                # Keep payment-related chunks
                if chunk_type not in ["table_row", "invoice_block", "paragraph"]:
                    # Skip non-relevant chunk types
                    if "payment" not in result.get("text", "").lower():
                        continue
            
            # Filter by entity matches (if query mentions PAN, GSTIN, etc.)
            if self._has_entity_matches(query, result):
                filtered.append(result)
                continue
            
            # Keep if similarity is high enough
            similarity = result.get("similarity", 0) or result.get("combined_score", 0)
            if similarity >= 0.4:  # Higher threshold for filtered results
                filtered.append(result)
        
        # Sort by similarity
        filtered.sort(key=lambda x: x.get("similarity", 0) or x.get("combined_score", 0), reverse=True)
        
        return filtered
    
    async def _pass_c_expansion(
        self,
        results: List[Dict[str, Any]],
        client_id: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Pass C: Expand context with neighboring chunks"""
        expanded = []
        seen_chunk_ids = set()
        
        for result in results:
            chunk_id = result.get("chunk_id")
            document_id = result.get("document_id")
            chunk_index = result.get("chunk_index", 0)
            chunk_metadata = result.get("metadata", {}) or {}
            
            # Add the original chunk
            if chunk_id not in seen_chunk_ids:
                expanded.append(result)
                seen_chunk_ids.add(chunk_id)
            
            # Get neighboring chunks (same page, adjacent indices)
            page = chunk_metadata.get("page")
            if page:
                # Get chunks from same page
                neighbors = await self._get_neighboring_chunks(
                    document_id, chunk_index, page, client_id
                )
                for neighbor in neighbors:
                    if neighbor.get("chunk_id") not in seen_chunk_ids:
                        expanded.append(neighbor)
                        seen_chunk_ids.add(neighbor.get("chunk_id"))
            
            # Get table headers if chunk is a table row
            if chunk_metadata.get("chunk_type") == "table_row":
                table_index = chunk_metadata.get("table_index")
                if table_index:
                    headers = await self._get_table_headers(document_id, table_index, client_id)
                    for header in headers:
                        if header.get("chunk_id") not in seen_chunk_ids:
                            expanded.append(header)
                            seen_chunk_ids.add(header.get("chunk_id"))
            
            # Get related vendor rows if chunk mentions vendor
            vendor = chunk_metadata.get("vendor") or self._extract_vendor_from_text(result.get("text", ""))
            if vendor:
                related = await self._get_related_vendor_chunks(vendor, document_id, client_id, limit=3)
                for rel in related:
                    if rel.get("chunk_id") not in seen_chunk_ids:
                        expanded.append(rel)
                        seen_chunk_ids.add(rel.get("chunk_id"))
            
            # Stop if we have enough chunks
            if len(expanded) >= limit:
                break
        
        return expanded[:limit]
    
    async def _get_neighboring_chunks(
        self,
        document_id: str,
        chunk_index: int,
        page: int,
        client_id: str,
        window: int = 2
    ) -> List[Dict[str, Any]]:
        """Get neighboring chunks from same page"""
        query = """
            SELECT 
                dc.id, dc.document_id, dc.chunk_index, dc.text, dc.metadata,
                d.client_id, d.period, d.category, d.doc_type
            FROM document_chunks dc
            LEFT JOIN documents d ON dc.document_id = d.id
            WHERE dc.document_id = ? 
            AND d.client_id = ?
            AND json_extract(dc.metadata, '$.page') = ?
            AND dc.chunk_index BETWEEN ? AND ?
            AND dc.id != (
                SELECT id FROM document_chunks 
                WHERE document_id = ? AND chunk_index = ?
            )
            ORDER BY dc.chunk_index
            LIMIT ?
        """
        
        rows = await self.db.fetchall(
            query,
            (document_id, client_id, page, chunk_index - window, chunk_index + window, document_id, chunk_index, window * 2)
        )
        
        results = []
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "text": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
                "client_id": row[5],
                "period": row[6],
                "category": row[7],
                "doc_type": row[8]
            })
        
        return results
    
    async def _get_table_headers(
        self,
        document_id: str,
        table_index: int,
        client_id: str
    ) -> List[Dict[str, Any]]:
        """Get table header chunks"""
        query = """
            SELECT 
                dc.id, dc.document_id, dc.chunk_index, dc.text, dc.metadata,
                d.client_id, d.period, d.category, d.doc_type
            FROM document_chunks dc
            LEFT JOIN documents d ON dc.document_id = d.id
            WHERE dc.document_id = ? 
            AND d.client_id = ?
            AND json_extract(dc.metadata, '$.table_index') = ?
            AND json_extract(dc.metadata, '$.row_index') = 0
            LIMIT 1
        """
        
        rows = await self.db.fetchall(query, (document_id, client_id, table_index))
        
        results = []
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "text": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
                "client_id": row[5],
                "period": row[6],
                "category": row[7],
                "doc_type": row[8]
            })
        
        return results
    
    async def _get_related_vendor_chunks(
        self,
        vendor: str,
        document_id: str,
        client_id: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get chunks related to same vendor"""
        query = """
            SELECT 
                dc.id, dc.document_id, dc.chunk_index, dc.text, dc.metadata,
                d.client_id, d.period, d.category, d.doc_type
            FROM document_chunks dc
            LEFT JOIN documents d ON dc.document_id = d.id
            WHERE d.client_id = ?
            AND (
                json_extract(dc.metadata, '$.vendor') = ?
                OR dc.text LIKE ?
            )
            AND dc.document_id != ?
            ORDER BY dc.chunk_index
            LIMIT ?
        """
        
        vendor_pattern = f"%{vendor}%"
        rows = await self.db.fetchall(
            query,
            (client_id, vendor, vendor_pattern, document_id, limit)
        )
        
        results = []
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "text": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
                "client_id": row[5],
                "period": row[6],
                "category": row[7],
                "doc_type": row[8]
            })
        
        return results
    
    def _extract_time_hints(self, query: str) -> List[str]:
        """Extract time/period hints from query"""
        # Look for year, quarter, month patterns
        year_pattern = r'\b(20\d{2})\b'
        quarter_pattern = r'\b(Q[1-4]|quarter\s*[1-4])\b'
        month_pattern = r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2}\b'
        
        hints = []
        hints.extend(re.findall(year_pattern, query))
        hints.extend(re.findall(quarter_pattern, query, re.IGNORECASE))
        hints.extend(re.findall(month_pattern, query, re.IGNORECASE))
        
        return hints
    
    def _period_matches(self, period: str, time_hints: List[str]) -> bool:
        """Check if period matches time hints"""
        period_lower = period.lower()
        for hint in time_hints:
            if hint.lower() in period_lower:
                return True
        return False
    
    def _has_entity_matches(self, query: str, result: Dict[str, Any]) -> bool:
        """Check if result has entities matching query"""
        # Extract entities from query
        query_entities = {
            "pan": re.findall(r'\b([A-Z]{5}\d{4}[A-Z])\b', query.upper()),
            "gstin": re.findall(r'\b([0-9A-Z]{15})\b', query.upper()),
            "invoice": re.findall(r'(?:invoice|bill)[\s#]*:?\s*([A-Z0-9\-/]+)', query, re.IGNORECASE),
        }
        
        # Check result metadata for entities
        metadata = result.get("metadata", {}) or {}
        entities = metadata.get("entities", {}) or {}
        
        # Check PAN
        if query_entities["pan"]:
            result_pans = [p.upper() for p in entities.get("pan_numbers", [])]
            if any(pan in result_pans for pan in query_entities["pan"]):
                return True
        
        # Check GSTIN
        if query_entities["gstin"]:
            result_gstins = [g.upper() for g in entities.get("gstin_numbers", [])]
            if any(gstin in result_gstins for gstin in query_entities["gstin"]):
                return True
        
        # Check invoice numbers
        if query_entities["invoice"]:
            result_invoices = [i.upper() for i in entities.get("invoice_numbers", [])]
            if any(inv in result_invoices for inv in query_entities["invoice"]):
                return True
        
        return False
    
    def _extract_vendor_from_text(self, text: str) -> Optional[str]:
        """Extract vendor name from text"""
        vendor_patterns = [
            r'(?:from|vendor|supplier)[\s]*:?\s*([A-Z][A-Za-z\s&]{2,30})',
        ]
        
        for pattern in vendor_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None

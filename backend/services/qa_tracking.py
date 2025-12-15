"""
Q&A Tracking - Store questions and answers with chunk references for traceability
"""

import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class QATracker:
    """Track questions and answers with chunk references"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize QA tracker
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
    
    async def store_qa(
        self,
        client_id: str,
        question: str,
        answer: str,
        chunk_ids: List[str],
        model_version: Optional[str] = None
    ) -> str:
        """
        Store a Q&A pair with chunk references
        
        Args:
            client_id: Client ID
            question: User question
            answer: LLM answer
            chunk_ids: List of chunk IDs used for context
            model_version: Model version used (optional)
        
        Returns:
            QA record ID
        """
        qa_id = str(uuid.uuid4())
        chunk_ids_json = json.dumps(chunk_ids)
        
        query = """
            INSERT INTO question_answers 
            (id, client_id, question, answer, chunk_ids, model_version)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        
        await self.db.execute(
            query,
            (qa_id, client_id, question, answer, chunk_ids_json, model_version)
        )
        
        logger.info(f"Stored Q&A {qa_id} for client {client_id} with {len(chunk_ids)} chunk references")
        return qa_id
    
    async def get_qa(self, qa_id: str) -> Optional[Dict[str, Any]]:
        """Get a Q&A record by ID"""
        query = """
            SELECT id, client_id, question, answer, chunk_ids, model_version, created_at
            FROM question_answers
            WHERE id = ?
        """
        
        row = await self.db.fetchone(query, (qa_id,))
        if not row:
            return None
        
        return {
            "id": row[0],
            "client_id": row[1],
            "question": row[2],
            "answer": row[3],
            "chunk_ids": json.loads(row[4]) if row[4] else [],
            "model_version": row[5],
            "created_at": row[6]
        }
    
    async def get_client_qa_history(
        self,
        client_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get Q&A history for a client"""
        query = """
            SELECT id, question, answer, chunk_ids, model_version, created_at
            FROM question_answers
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        
        rows = await self.db.fetchall(query, (client_id, limit, offset))
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "question": row[1],
                "answer": row[2],
                "chunk_ids": json.loads(row[3]) if row[3] else [],
                "model_version": row[4],
                "created_at": row[5]
            })
        
        return results
    
    async def get_chunks_for_qa(self, qa_id: str) -> List[Dict[str, Any]]:
        """Get all chunks referenced in a Q&A"""
        qa = await self.get_qa(qa_id)
        if not qa:
            return []
        
        chunk_ids = qa.get("chunk_ids", [])
        if not chunk_ids:
            return []
        
        # Build query with IN clause
        placeholders = ",".join("?" * len(chunk_ids))
        query = f"""
            SELECT 
                dc.id, dc.document_id, dc.chunk_index, dc.text, dc.metadata,
                d.client_id, d.period, d.category, d.doc_type, d.file_path
            FROM document_chunks dc
            LEFT JOIN documents d ON dc.document_id = d.id
            WHERE dc.id IN ({placeholders})
            ORDER BY dc.chunk_index
        """
        
        rows = await self.db.fetchall(query, tuple(chunk_ids))
        
        chunks = []
        for row in rows:
            chunks.append({
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "text": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
                "client_id": row[5],
                "period": row[6],
                "category": row[7],
                "doc_type": row[8],
                "file_path": row[9]
            })
        
        return chunks
    
    async def get_similar_questions(
        self,
        question: str,
        client_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get similar questions from history (simple keyword matching)"""
        query_parts = []
        params = []
        
        if client_id:
            query_parts.append("client_id = ?")
            params.append(client_id)
        
        # Simple keyword matching (could be enhanced with embeddings)
        keywords = question.lower().split()
        keyword_conditions = []
        for keyword in keywords[:5]:  # Limit to first 5 keywords
            keyword_conditions.append("LOWER(question) LIKE ?")
            params.append(f"%{keyword}%")
        
        if keyword_conditions:
            query_parts.append(f"({' OR '.join(keyword_conditions)})")
        
        where_clause = " AND ".join(query_parts) if query_parts else "1=1"
        
        query = f"""
            SELECT id, question, answer, created_at
            FROM question_answers
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        rows = await self.db.fetchall(query, tuple(params))
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "question": row[1],
                "answer": row[2],
                "created_at": row[3]
            })
        
        return results
    
    async def delete_qa(self, qa_id: str, client_id: str) -> bool:
        """Delete a Q&A record"""
        query = """
            DELETE FROM question_answers
            WHERE id = ? AND client_id = ?
        """
        
        cursor = await self.db.execute(query, (qa_id, client_id))
        deleted = cursor.rowcount > 0
        
        if deleted:
            logger.info(f"Deleted Q&A {qa_id} for client {client_id}")
        
        return deleted

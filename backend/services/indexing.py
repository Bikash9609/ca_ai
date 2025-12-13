"""
Document Indexing - Vector storage and indexing in SQLite
"""

import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import json
import uuid
from datetime import datetime

from database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class VectorStorage:
    """Store and retrieve vector embeddings in SQLite"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize vector storage
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension
    
    async def initialize(self) -> None:
        """Initialize vector storage tables"""
        # Ensure document_chunks table exists (should be in schema)
        # We'll store embeddings as BLOB in document_chunks.embedding
        pass
    
    def _embedding_to_blob(self, embedding: np.ndarray) -> bytes:
        """Convert numpy array to BLOB"""
        return embedding.tobytes()
    
    def _blob_to_embedding(self, blob: bytes) -> np.ndarray:
        """Convert BLOB to numpy array"""
        return np.frombuffer(blob, dtype=np.float32)
    
    async def store_chunk(
        self,
        document_id: str,
        chunk_index: int,
        text: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a document chunk with embedding
        
        Args:
            document_id: Document ID
            chunk_index: Chunk index
            text: Chunk text
            embedding: Embedding vector
            metadata: Chunk metadata
        
        Returns:
            Chunk ID
        """
        chunk_id = str(uuid.uuid4())
        embedding_blob = self._embedding_to_blob(embedding)
        metadata_json = json.dumps(metadata) if metadata else None
        
        query = """
            INSERT INTO document_chunks (id, document_id, chunk_index, text, embedding, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        
        await self.db.execute(
            query,
            (chunk_id, document_id, chunk_index, text, embedding_blob, metadata_json)
        )
        
        # Get the INTEGER rowid for FTS5 (SQLite assigns rowid even with TEXT primary key)
        row = await self.db.fetchone(
            "SELECT rowid FROM document_chunks WHERE id = ?",
            (chunk_id,)
        )
        chunk_rowid = row[0] if row else None
        
        # Update FTS5 index
        if chunk_rowid:
            await self.db.execute(
                "INSERT INTO document_fts (rowid, text) VALUES (?, ?)",
                (chunk_rowid, text)
            )
        
        logger.debug(f"Stored chunk {chunk_id} for document {document_id}")
        return chunk_id
    
    async def store_chunks_batch(
        self,
        document_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[np.ndarray]
    ) -> List[str]:
        """
        Store multiple chunks in batch
        
        Args:
            document_id: Document ID
            chunks: List of chunk dictionaries
            embeddings: List of embedding vectors
        
        Returns:
            List of chunk IDs
        """
        chunk_ids = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_index = chunk.get("chunk_index", i)
            print(f"[VECTOR STORAGE] Storing chunk {i+1}/{len(chunks)} - chunk_index: {chunk_index}, vector shape: {embedding.shape}, vector sample (first 5 values): {embedding[:5].tolist()}")
            chunk_id = await self.store_chunk(
                document_id,
                chunk_index,
                chunk["text"],
                embedding,
                chunk.get("metadata")
            )
            chunk_ids.append(chunk_id)
            print(f"[VECTOR STORAGE] Stored chunk with ID: {chunk_id}")
        
        return chunk_ids
    
    async def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a chunk by ID"""
        query = """
            SELECT id, document_id, chunk_index, text, embedding, metadata
            FROM document_chunks
            WHERE id = ?
        """
        
        row = await self.db.fetchone(query, (chunk_id,))
        if not row:
            return None
        
        chunk = {
            "id": row[0],
            "document_id": row[1],
            "chunk_index": row[2],
            "text": row[3],
            "metadata": json.loads(row[5]) if row[5] else None
        }
        
        if row[4]:  # embedding
            chunk["embedding"] = self._blob_to_embedding(row[4])
        
        return chunk
    
    async def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a document"""
        query = """
            SELECT id, chunk_index, text, embedding, metadata
            FROM document_chunks
            WHERE document_id = ?
            ORDER BY chunk_index
        """
        
        rows = await self.db.fetchall(query, (document_id,))
        chunks = []
        
        for row in rows:
            chunk = {
                "id": row[0],
                "chunk_index": row[1],
                "text": row[2],
                "metadata": json.loads(row[4]) if row[4] else None
            }
            if row[3]:  # embedding
                chunk["embedding"] = self._blob_to_embedding(row[3])
            chunks.append(chunk)
        
        return chunks
    
    async def delete_document_chunks(self, document_id: str) -> None:
        """Delete all chunks for a document"""
        # Get rowids for FTS5 deletion
        chunk_rowids = await self.db.fetchall(
            "SELECT rowid FROM document_chunks WHERE document_id = ?",
            (document_id,)
        )
        
        # Delete from document_chunks
        await self.db.execute(
            "DELETE FROM document_chunks WHERE document_id = ?",
            (document_id,)
        )
        
        # Delete from FTS5
        for row in chunk_rowids:
            await self.db.execute(
                "DELETE FROM document_fts WHERE rowid = ?",
                (row[0],)
            )
        
        logger.info(f"Deleted chunks for document {document_id}")


class DocumentIndexer:
    """Index documents with embeddings and full-text search"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        embedding_generator,
        chunker
    ):
        """
        Initialize document indexer
        
        Args:
            db_manager: Database manager
            embedding_generator: EmbeddingGenerator instance
            chunker: DocumentChunker instance
        """
        self.db = db_manager
        self.embedding_gen = embedding_generator
        self.chunker = chunker
        self.vector_storage = VectorStorage(db_manager)
    
    async def index_document(
        self,
        document_id: str,
        text: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Index a document (chunk, embed, and store)
        
        Args:
            document_id: Document ID
            text: Document text
            document_metadata: Document metadata
        
        Returns:
            Indexing result with chunk count
        """
        # Chunk the document
        print(f"[INDEXING] Step 1: Chunking document {document_id}")
        chunks = self.chunker.chunk_document(document_id, text, document_metadata)
        
        if not chunks:
            logger.warning(f"No chunks created for document {document_id}")
            print(f"[INDEXING] No chunks created for document {document_id}")
            return {"chunks_created": 0, "chunk_ids": []}
        
        print(f"[INDEXING] Chunking completed. Created {len(chunks)} chunks")
        chunk_indexes = [chunk.get("chunk_index", i) for i, chunk in enumerate(chunks)]
        print(f"[INDEXING] Generated chunk indexes: {chunk_indexes}")
        
        # Generate embeddings for chunks
        print(f"[INDEXING] Step 2: Generating embeddings for {len(chunks)} chunks")
        chunk_texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedding_gen.generate_batch(chunk_texts)
        print(f"[INDEXING] Embeddings generated: {len(embeddings)} vectors")
        
        # Store chunks with embeddings
        print(f"[INDEXING] Step 3: Storing chunks with embeddings")
        chunk_ids = await self.vector_storage.store_chunks_batch(
            document_id,
            chunks,
            embeddings
        )
        
        print(f"[INDEXING] Storage completed. Stored {len(chunk_ids)} chunks with IDs: {chunk_ids}")
        logger.info(f"Indexed document {document_id}: {len(chunk_ids)} chunks")
        
        return {
            "chunks_created": len(chunk_ids),
            "chunk_ids": chunk_ids
        }
    
    async def reindex_document(
        self,
        document_id: str,
        text: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Reindex a document (delete old chunks and create new ones)"""
        # Delete existing chunks
        await self.vector_storage.delete_document_chunks(document_id)
        
        # Index again
        return await self.index_document(document_id, text, document_metadata)

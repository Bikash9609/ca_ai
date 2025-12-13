"""
Text Chunking Strategy - Smart text splitting with overlap and metadata preservation
"""

import re
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TextChunker:
    """Smart text chunking with overlap handling"""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None
    ):
        """
        Initialize text chunker
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap size between chunks
            separators: List of separators to split on (in order of preference)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or [
            "\n\n",  # Paragraph breaks
            "\n",    # Line breaks
            ". ",    # Sentence endings
            " ",     # Word boundaries
            ""       # Character boundaries (fallback)
        ]
    
    def split_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks with metadata
        
        Args:
            text: Text to split
            metadata: Metadata to attach to each chunk
        
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if not text or not text.strip():
            return []
        
        chunks = []
        current_chunk = ""
        current_length = 0
        chunk_index = 0
        
        # Split by preferred separators
        parts = self._split_by_separators(text)
        
        for part in parts:
            part_length = len(part)
            
            # If part itself is larger than chunk size, split it further
            if part_length > self.chunk_size:
                # Save current chunk if any
                if current_chunk:
                    chunks.append(self._create_chunk(
                        current_chunk.strip(),
                        chunk_index,
                        metadata
                    ))
                    chunk_index += 1
                    current_chunk = ""
                    current_length = 0
                
                # Split large part
                sub_chunks = self._split_large_text(part, chunk_index, metadata)
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
                continue
            
            # Check if adding this part would exceed chunk size
            if current_length + part_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(self._create_chunk(
                    current_chunk.strip(),
                    chunk_index,
                    metadata
                ))
                chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + part
                    current_length = len(current_chunk)
                else:
                    current_chunk = part
                    current_length = part_length
            else:
                current_chunk += part
                current_length += part_length
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(self._create_chunk(
                current_chunk.strip(),
                chunk_index,
                metadata
            ))
        
        return chunks
    
    def _split_by_separators(self, text: str) -> List[str]:
        """Split text by separators in order of preference"""
        parts = [text]
        
        for separator in self.separators:
            if separator == "":
                # Character-level splitting (fallback)
                continue
            
            new_parts = []
            for part in parts:
                if separator in part:
                    split_parts = part.split(separator)
                    # Rejoin with separator except for last part
                    for i, split_part in enumerate(split_parts):
                        if i < len(split_parts) - 1:
                            new_parts.append(split_part + separator)
                        else:
                            new_parts.append(split_part)
                else:
                    new_parts.append(part)
            parts = new_parts
        
        return [p for p in parts if p.strip()]
    
    def _split_large_text(
        self,
        text: str,
        start_index: int,
        metadata: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Split text that's larger than chunk size"""
        chunks = []
        chunk_index = start_index
        
        # Split by sentences first
        sentences = re.split(r'([.!?]\s+)', text)
        current_chunk = ""
        current_length = 0
        
        i = 0
        while i < len(sentences):
            sentence = sentences[i]
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunks.append(self._create_chunk(
                    current_chunk.strip(),
                    chunk_index,
                    metadata
                ))
                chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + sentence
                    current_length = len(current_chunk)
                else:
                    current_chunk = sentence
                    current_length = sentence_length
            else:
                current_chunk += sentence
                current_length += sentence_length
            
            i += 1
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(self._create_chunk(
                current_chunk.strip(),
                chunk_index,
                metadata
            ))
        
        return chunks
    
    def _create_chunk(
        self,
        text: str,
        chunk_index: int,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create a chunk dictionary with metadata"""
        chunk = {
            "text": text,
            "chunk_index": chunk_index,
            "length": len(text)
        }
        
        if metadata:
            chunk["metadata"] = metadata.copy()
        
        return chunk


class DocumentChunker:
    """Chunk documents with metadata preservation"""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        """
        Initialize document chunker
        
        Args:
            chunk_size: Target chunk size
            chunk_overlap: Overlap size
        """
        self.chunker = TextChunker(chunk_size, chunk_overlap)
    
    def chunk_document(
        self,
        document_id: str,
        text: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk a document with metadata
        
        Args:
            document_id: Document ID
            text: Document text
            document_metadata: Document-level metadata
        
        Returns:
            List of chunks with metadata
        """
        # Prepare chunk metadata
        chunk_metadata = {
            "document_id": document_id
        }
        
        if document_metadata:
            # Include relevant document metadata
            chunk_metadata.update({
                k: v for k, v in document_metadata.items()
                if k in ['client_id', 'period', 'doc_type', 'category', 'file_path']
            })
        
        # Split text into chunks
        chunks = self.chunker.split_text(text, chunk_metadata)
        
        # Add document-level context to each chunk
        for chunk in chunks:
            chunk["document_id"] = document_id
            if document_metadata:
                chunk["document_metadata"] = document_metadata
        
        print(f"[CHUNKING] Document {document_id}: Created {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            chunk_idx = chunk.get("chunk_index", i)
            chunk_len = len(chunk.get("text", ""))
            print(f"[CHUNKING] Chunk {i+1}: index={chunk_idx}, length={chunk_len} chars, preview={chunk.get('text', '')[:50]}...")
        
        return chunks

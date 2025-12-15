"""
Context Packer - Assemble context bundles for LLM in Cursor-style format
"""

from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ContextPacker:
    """Pack context chunks into LLM-friendly format"""
    
    def pack_context(
        self,
        chunks: List[Dict[str, Any]],
        question: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Pack context chunks into a formatted prompt
        
        Args:
            chunks: List of context chunks from retrieval
            question: User question
            system_prompt: Optional system prompt (default CA assistant prompt)
        
        Returns:
            Formatted context string for LLM
        """
        if not chunks:
            return self._pack_empty_context(question, system_prompt)
        
        # Build context sections
        context_sections = []
        
        for i, chunk in enumerate(chunks, 1):
            chunk_text = self._format_chunk(chunk, i)
            context_sections.append(chunk_text)
        
        # Assemble full prompt
        context_text = "\n\n".join(context_sections)
        
        # Build final prompt
        if system_prompt:
            system = system_prompt
        else:
            system = self._get_default_system_prompt()
        
        full_prompt = f"""{system}

CONTEXT:
{context_text}

QUESTION:
{question}

Please answer based ONLY on the provided context. If information is missing, state that clearly."""
        
        return full_prompt
    
    def _format_chunk(self, chunk: Dict[str, Any], index: int) -> str:
        """Format a single chunk with metadata"""
        text = chunk.get("text", "")
        metadata = chunk.get("metadata", {}) or {}
        
        # Build chunk header with metadata
        header_parts = []
        
        # Document type
        doc_type = chunk.get("doc_type", "")
        if doc_type:
            header_parts.append(doc_type)
        
        # Page number
        page = metadata.get("page")
        if page:
            header_parts.append(f"page {page}")
        
        # Chunk type
        chunk_type = metadata.get("chunk_type", "")
        if chunk_type:
            type_labels = {
                "table_row": "table row",
                "invoice_block": "invoice",
                "paragraph": "text",
                "page": "page content"
            }
            header_parts.append(type_labels.get(chunk_type, chunk_type))
        
        # Vendor name
        vendor = metadata.get("vendor")
        if vendor:
            header_parts.append(f"vendor: {vendor}")
        
        # Build header
        if header_parts:
            header = f"[Chunk {index} – {' '.join(header_parts)}]"
        else:
            header = f"[Chunk {index}]"
        
        return f"{header}\n{text}"
    
    def _pack_empty_context(self, question: str, system_prompt: Optional[str] = None) -> str:
        """Pack context when no chunks found"""
        if system_prompt:
            system = system_prompt
        else:
            system = self._get_default_system_prompt()
        
        return f"""{system}

CONTEXT:
No relevant documents found in the uploaded files.

QUESTION:
{question}

Please inform the user that no relevant information was found in the uploaded documents."""
    
    def _get_default_system_prompt(self) -> str:
        """Get default CA assistant system prompt"""
        return """You are a CA's AI assistant for GST and TDS compliance and financial analysis.

CORE PROTOCOL:
1. MANDATORY: Use ONLY the provided context. Never assume facts not in context.
2. ADVISORY ONLY: This is assistance, not professional advice. CA must approve all actions.
3. UNCERTAINTY: If information is missing or unclear, state that explicitly.
4. SOURCE CITATION: Reference page numbers and document types when possible.

When answering:
- Cite page numbers: "Based on AWS invoices on pages 3–5..."
- Mention uncertainty: "PAN not found in uploaded docs — please confirm"
- Reference sources: "See chunk from document XYZ, page 3"
- Never auto-file or auto-decide — always require CA approval"""
    
    def pack_context_for_tool_calling(
        self,
        chunks: List[Dict[str, Any]],
        question: str
    ) -> List[Dict[str, Any]]:
        """
        Pack context for tool-calling LLM (returns structured format)
        
        Args:
            chunks: List of context chunks
            question: User question
        
        Returns:
            List of messages for LLM (system + context + user)
        """
        messages = []
        
        # System message
        messages.append({
            "role": "system",
            "content": self._get_default_system_prompt()
        })
        
        # Context as user message (structured)
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            chunk_info = self._format_chunk_info(chunk, i)
            context_parts.append(chunk_info)
        
        if context_parts:
            context_text = "\n\n".join(context_parts)
            messages.append({
                "role": "user",
                "content": f"CONTEXT:\n{context_text}\n\nQUESTION:\n{question}"
            })
        else:
            messages.append({
                "role": "user",
                "content": f"CONTEXT:\nNo relevant documents found.\n\nQUESTION:\n{question}"
            })
        
        return messages
    
    def _format_chunk_info(self, chunk: Dict[str, Any], index: int) -> str:
        """Format chunk info for tool-calling format"""
        text = chunk.get("text", "")
        metadata = chunk.get("metadata", {}) or {}
        
        info_parts = [f"Chunk {index}:"]
        
        # Add metadata
        if metadata.get("page"):
            info_parts.append(f"Page {metadata['page']}")
        if chunk.get("doc_type"):
            info_parts.append(f"Type: {chunk['doc_type']}")
        if metadata.get("chunk_type"):
            info_parts.append(f"Chunk type: {metadata['chunk_type']}")
        
        info_parts.append(f"\n{text}")
        
        return " ".join(info_parts)
    
    def get_chunk_references(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Get human-readable references for chunks (for answer citation)
        
        Args:
            chunks: List of chunks
        
        Returns:
            List of reference strings like "Document XYZ, page 3"
        """
        references = []
        
        for chunk in chunks:
            ref_parts = []
            
            doc_type = chunk.get("doc_type", "")
            if doc_type:
                ref_parts.append(doc_type)
            
            metadata = chunk.get("metadata", {}) or {}
            page = metadata.get("page")
            if page:
                ref_parts.append(f"page {page}")
            
            if ref_parts:
                references.append(", ".join(ref_parts))
            else:
                references.append("document")
        
        return references

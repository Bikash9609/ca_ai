"""
Text Chunking Strategy - Smart text splitting with overlap and metadata preservation
"""

import re
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path

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
    """Chunk documents with metadata preservation - uses SmartDocumentChunker when parsed data available"""
    
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
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunker = TextChunker(chunk_size, chunk_overlap)
        self.smart_chunker = SmartDocumentChunker(chunk_size, chunk_overlap)
    
    def chunk_document(
        self,
        document_id: str,
        text: str,
        document_metadata: Optional[Dict[str, Any]] = None,
        parsed_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk a document with metadata
        
        Args:
            document_id: Document ID
            text: Document text
            document_metadata: Document-level metadata
            parsed_data: Parsed document data (with page/table info) for smart chunking
        
        Returns:
            List of chunks with metadata
        """
        # Use smart chunker if parsed_data is available
        if parsed_data:
            return self.smart_chunker.chunk_document(document_id, text, document_metadata, parsed_data)
        
        # Fallback to standard chunking
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


class SmartDocumentChunker:
    """Smart chunking with page/table/section awareness"""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        """
        Initialize smart document chunker
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap size between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.fallback_chunker = TextChunker(chunk_size, chunk_overlap)
    
    def chunk_document(
        self,
        document_id: str,
        text: str,
        document_metadata: Optional[Dict[str, Any]] = None,
        parsed_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk a document with smart strategies based on document type
        
        Args:
            document_id: Document ID
            text: Document text
            document_metadata: Document-level metadata
            parsed_data: Parsed document data (from parser) with page/table info
        
        Returns:
            List of chunks with enhanced metadata
        """
        file_type = document_metadata.get("file_type", "") if document_metadata else ""
        
        # Prepare base chunk metadata
        base_metadata = {
            "document_id": document_id
        }
        if document_metadata:
            base_metadata.update({
                k: v for k, v in document_metadata.items()
                if k in ['client_id', 'period', 'doc_type', 'category', 'file_path']
            })
        
        # Choose chunking strategy based on file type
        if file_type == 'pdf' and parsed_data:
            chunks = self._chunk_pdf(text, parsed_data, base_metadata)
        elif file_type in ['xlsx', 'xls'] and parsed_data:
            chunks = self._chunk_excel(text, parsed_data, base_metadata)
        else:
            # Fallback to standard chunking
            chunks = self.fallback_chunker.split_text(text, base_metadata)
        
        # Add document-level context to each chunk
        for chunk in chunks:
            chunk["document_id"] = document_id
            if document_metadata:
                chunk["document_metadata"] = document_metadata
        
        logger.info(f"[SMART CHUNKING] Document {document_id}: Created {len(chunks)} chunks")
        return chunks
    
    def _chunk_pdf(
        self,
        text: str,
        parsed_data: Dict[str, Any],
        base_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chunk PDF with page/table/section awareness"""
        chunks = []
        chunk_index = 0
        
        # Get page texts if available
        page_texts = parsed_data.get("page_texts", [])
        tables = parsed_data.get("tables", [])
        
        if not page_texts:
            # Fallback: split by page breaks in text
            page_breaks = text.split("\n\n--- Page Break ---\n\n")
            page_texts = [
                {"page": i + 1, "text": page_text, "start_char": 0, "end_char": len(page_text)}
                for i, page_text in enumerate(page_breaks)
            ]
        
        # Create a map of tables by page
        tables_by_page = {}
        for table in tables:
            page_num = table.get("page", 0)
            if page_num not in tables_by_page:
                tables_by_page[page_num] = []
            tables_by_page[page_num].append(table)
        
        # Chunk each page
        for page_info in page_texts:
            page_num = page_info.get("page", 0)
            page_text = page_info.get("text", "")
            start_char = page_info.get("start_char", 0)
            
            if not page_text.strip():
                continue
            
            # Check if this page has tables
            page_tables = tables_by_page.get(page_num, [])
            
            if page_tables:
                # Table-aware chunking
                chunks.extend(self._chunk_page_with_tables(
                    page_num, page_text, page_tables, start_char, base_metadata, chunk_index
                ))
                chunk_index += len(chunks) - chunk_index
            else:
                # Section-based chunking for text-only pages
                page_chunks = self._chunk_page_by_sections(
                    page_num, page_text, start_char, base_metadata, chunk_index
                )
                chunks.extend(page_chunks)
                chunk_index += len(page_chunks)
        
        return chunks
    
    def _chunk_page_with_tables(
        self,
        page_num: int,
        page_text: str,
        tables: List[Dict[str, Any]],
        start_char: int,
        base_metadata: Dict[str, Any],
        start_index: int
    ) -> List[Dict[str, Any]]:
        """Chunk a page that contains tables"""
        chunks = []
        chunk_index = start_index
        current_pos = 0
        
        # Sort tables by position (if available) or process in order
        for table_idx, table in enumerate(tables):
            table_data = table.get("data", [])
            table_start_marker = f"Table {table_idx + 1}"
            
            # Find table position in text
            table_pos = page_text.find(table_start_marker, current_pos)
            if table_pos == -1:
                # Try to find table by looking for table-like patterns
                table_pos = current_pos
            
            # Chunk text before table
            if table_pos > current_pos:
                pre_table_text = page_text[current_pos:table_pos].strip()
                if pre_table_text:
                    pre_chunks = self._chunk_text_by_sections(
                        pre_table_text, page_num, current_pos + start_char, base_metadata, chunk_index
                    )
                    chunks.extend(pre_chunks)
                    chunk_index += len(pre_chunks)
            
            # Chunk table rows
            if table_data:
                header_row = table_data[0] if table_data else []
                header_text = " | ".join(str(cell) if cell else "" for cell in header_row)
                
                for row_idx, row in enumerate(table_data[1:], 1):  # Skip header
                    row_text = " | ".join(str(cell) if cell else "" for cell in row)
                    full_row_text = f"{header_text}\n{row_text}" if header_text else row_text
                    
                    chunk = {
                        "text": full_row_text,
                        "chunk_index": chunk_index,
                        "length": len(full_row_text),
                        "metadata": {
                            **base_metadata,
                            "chunk_type": "table_row",
                            "page": page_num,
                            "table_index": table_idx + 1,
                            "row_index": row_idx,
                            "start_char": start_char + table_pos,
                            "end_char": start_char + table_pos + len(full_row_text)
                        }
                    }
                    chunks.append(chunk)
                    chunk_index += 1
            
            current_pos = table_pos + len(table_start_marker)
        
        # Chunk remaining text after last table
        if current_pos < len(page_text):
            remaining_text = page_text[current_pos:].strip()
            if remaining_text:
                remaining_chunks = self._chunk_text_by_sections(
                    remaining_text, page_num, current_pos + start_char, base_metadata, chunk_index
                )
                chunks.extend(remaining_chunks)
        
        return chunks
    
    def _chunk_page_by_sections(
        self,
        page_num: int,
        page_text: str,
        start_char: int,
        base_metadata: Dict[str, Any],
        start_index: int
    ) -> List[Dict[str, Any]]:
        """Chunk a page by detecting sections"""
        return self._chunk_text_by_sections(page_text, page_num, start_char, base_metadata, start_index)
    
    def _chunk_text_by_sections(
        self,
        text: str,
        page_num: int,
        start_char: int,
        base_metadata: Dict[str, Any],
        start_index: int
    ) -> List[Dict[str, Any]]:
        """Chunk text by detecting sections and invoice blocks"""
        chunks = []
        chunk_index = start_index
        
        # Detect invoice blocks (common patterns)
        invoice_patterns = [
            r'(?i)(invoice|bill|receipt)[\s#]*:?\s*([A-Z0-9\-/]+)',
            r'(?i)(invoice\s*date|bill\s*date)[\s:]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        ]
        
        # Detect section headers (lines that are all caps, short, followed by content)
        section_pattern = r'^([A-Z][A-Z\s]{2,30})\s*$'
        
        # Split by sections first
        lines = text.split('\n')
        sections = []
        current_section = {"header": None, "content": []}
        
        for line in lines:
            # Check if line is a section header
            if re.match(section_pattern, line.strip()):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"header": line.strip(), "content": []}
            else:
                current_section["content"].append(line)
        
        if current_section["content"]:
            sections.append(current_section)
        
        # If no sections detected, try invoice block detection
        if len(sections) == 1 and not sections[0]["header"]:
            # Try to detect invoice blocks
            invoice_blocks = self._detect_invoice_blocks(text)
            if invoice_blocks:
                for block in invoice_blocks:
                    chunk = {
                        "text": block["text"],
                        "chunk_index": chunk_index,
                        "length": len(block["text"]),
                        "metadata": {
                            **base_metadata,
                            "chunk_type": "invoice_block",
                            "page": page_num,
                            "start_char": start_char + block.get("offset", 0),
                            "end_char": start_char + block.get("offset", 0) + len(block["text"])
                        }
                    }
                    chunks.append(chunk)
                    chunk_index += 1
                return chunks
        
        # Chunk each section
        current_char_offset = 0
        for section in sections:
            section_text = '\n'.join(section["content"])
            if not section_text.strip():
                continue
            
            # If section is small enough, make it one chunk
            if len(section_text) <= self.chunk_size:
                chunk = {
                    "text": section_text,
                    "chunk_index": chunk_index,
                    "length": len(section_text),
                    "metadata": {
                        **base_metadata,
                        "chunk_type": "paragraph",
                        "page": page_num,
                        "section": section["header"],
                        "start_char": start_char + current_char_offset,
                        "end_char": start_char + current_char_offset + len(section_text)
                    }
                }
                chunks.append(chunk)
                chunk_index += 1
            else:
                # Split large section using fallback chunker
                section_chunks = self.fallback_chunker.split_text(section_text, base_metadata)
                for sc in section_chunks:
                    sc["metadata"] = {
                        **base_metadata,
                        "chunk_type": "paragraph",
                        "page": page_num,
                        "section": section["header"],
                        "start_char": start_char + current_char_offset,
                        "end_char": start_char + current_char_offset + len(sc["text"])
                    }
                    sc["chunk_index"] = chunk_index
                    chunks.append(sc)
                    chunk_index += 1
            
            current_char_offset += len(section_text) + 1  # +1 for newline
        
        return chunks
    
    def _detect_invoice_blocks(self, text: str) -> List[Dict[str, Any]]:
        """Detect invoice blocks in text"""
        blocks = []
        
        # Look for invoice number patterns
        invoice_pattern = r'(?i)(?:invoice|bill|receipt)[\s#]*:?\s*([A-Z0-9\-/]+)'
        matches = list(re.finditer(invoice_pattern, text))
        
        if not matches:
            return blocks
        
        # Group text around each invoice marker
        for i, match in enumerate(matches):
            start_pos = match.start()
            end_pos = match.end()
            
            # Find next invoice or end of text
            if i + 1 < len(matches):
                next_start = matches[i + 1].start()
            else:
                next_start = len(text)
            
            # Extract block (from current match to next match or reasonable size)
            block_text = text[start_pos:next_start]
            
            # Limit block size
            if len(block_text) > self.chunk_size * 2:
                block_text = block_text[:self.chunk_size * 2]
            
            blocks.append({
                "text": block_text.strip(),
                "offset": start_pos
            })
        
        return blocks
    
    def _chunk_excel(
        self,
        text: str,
        parsed_data: Dict[str, Any],
        base_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chunk Excel with row-based strategy"""
        chunks = []
        chunk_index = 0
        
        records = parsed_data.get("records", [])
        schema_type = parsed_data.get("schema_type", "generic")
        
        if not records:
            # Fallback to text chunking
            return self.fallback_chunker.split_text(text, base_metadata)
        
        # Get header row if available
        columns = parsed_data.get("columns", [])
        header_text = " | ".join(columns) if columns else ""
        
        # Group records by vendor/period if applicable
        if schema_type == "gstr2b" and records:
            # Group by vendor (GSTIN)
            vendor_groups = {}
            for record in records:
                vendor = record.get("gstin") or record.get("vendor_name") or "unknown"
                if vendor not in vendor_groups:
                    vendor_groups[vendor] = []
                vendor_groups[vendor].append(record)
            
            # Create chunks per vendor group
            for vendor, vendor_records in vendor_groups.items():
                # Header + records
                group_text = header_text + "\n" if header_text else ""
                group_text += "\n".join([
                    " | ".join([str(record.get(col, "")) for col in columns])
                    for record in vendor_records[:50]  # Limit per chunk
                ])
                
                chunk = {
                    "text": group_text,
                    "chunk_index": chunk_index,
                    "length": len(group_text),
                    "metadata": {
                        **base_metadata,
                        "chunk_type": "table_row",
                        "table_index": 1,
                        "vendor": vendor,
                        "row_count": len(vendor_records)
                    }
                }
                chunks.append(chunk)
                chunk_index += 1
        else:
            # Row-based chunking: one chunk per row or small group
            current_chunk_text = header_text + "\n" if header_text else ""
            current_chunk_rows = []
            
            for row_idx, record in enumerate(records):
                row_text = " | ".join([str(record.get(col, "")) for col in columns]) if columns else str(record)
                
                # If adding this row would exceed chunk size, save current chunk
                if len(current_chunk_text) + len(row_text) > self.chunk_size and current_chunk_rows:
                    chunk = {
                        "text": current_chunk_text.strip(),
                        "chunk_index": chunk_index,
                        "length": len(current_chunk_text),
                        "metadata": {
                            **base_metadata,
                            "chunk_type": "table_row",
                            "table_index": 1,
                            "row_index": current_chunk_rows[0],
                            "row_count": len(current_chunk_rows)
                        }
                    }
                    chunks.append(chunk)
                    chunk_index += 1
                    
                    # Start new chunk
                    current_chunk_text = header_text + "\n" if header_text else ""
                    current_chunk_rows = []
                
                current_chunk_text += row_text + "\n"
                current_chunk_rows.append(row_idx)
            
            # Add final chunk
            if current_chunk_text.strip():
                chunk = {
                    "text": current_chunk_text.strip(),
                    "chunk_index": chunk_index,
                    "length": len(current_chunk_text),
                    "metadata": {
                        **base_metadata,
                        "chunk_type": "table_row",
                        "table_index": 1,
                        "row_index": current_chunk_rows[0] if current_chunk_rows else 0,
                        "row_count": len(current_chunk_rows)
                    }
                }
                chunks.append(chunk)
        
        return chunks

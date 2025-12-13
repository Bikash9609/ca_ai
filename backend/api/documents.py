"""
Document API routes - Upload, list, and manage documents
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import hashlib
import json
from pathlib import Path
import uuid
from datetime import datetime

from core.workspace import WorkspaceManager, get_default_workspace_path
from database.connection import DatabaseManager
from services.classification import DocumentClassifier
from services.ocr import OCREngine
from services.parser import DocumentParser
from services.indexing import DocumentIndexer
from services.embedding import EmbeddingGenerator
from services.chunking import DocumentChunker
from services.queue import ProcessingQueue, ProcessingTask
import logging
import re

logger = logging.getLogger(__name__)

router = APIRouter()


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Sanitize a string to be filesystem-safe"""
    # Remove or replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove leading/trailing spaces and dots
    name = name.strip('. ')
    # Replace multiple spaces/underscores with single underscore
    name = re.sub(r'[\s_]+', '_', name)
    # Truncate if too long
    if len(name) > max_length:
        name = name[:max_length]
    return name


def extract_document_metadata(file_path: Path, classification: dict, parser: DocumentParser) -> dict:
    """Extract metadata from document for filename generation"""
    metadata = {
        "doc_type": classification.get("doc_type", {}).get("doc_type", "document"),
        "period": classification.get("category", {}).get("period", {}).get("period") if classification.get("category", {}).get("period") else None,
        "category": classification.get("category", {}).get("category", "general"),
        "invoice_number": None,
        "invoice_date": None,
        "vendor_name": None,
        "gstin": None,
    }
    
    try:
        file_ext = file_path.suffix.lower().lstrip('.')
        
        # Try to parse document to extract more details
        if file_ext in ['xlsx', 'xls']:
            parsed = parser.parse(file_path)
            if "records" in parsed and parsed["records"]:
                # Get first record for metadata
                first_record = parsed["records"][0]
                metadata["invoice_number"] = first_record.get("invoice_number") or first_record.get("invoice_no")
                metadata["invoice_date"] = first_record.get("invoice_date") or first_record.get("date")
                metadata["gstin"] = first_record.get("gstin") or first_record.get("supplier_gstin")
        
        elif file_ext == 'pdf':
            # Try to extract text from PDF
            try:
                parsed = parser.parse(file_path)
                text = parsed.get("text", "")
                
                # Extract invoice number
                invoice_patterns = [
                    r'(?:invoice|bill|inv)[\s#]*:?[\s]*([A-Z0-9\-/]+)',
                    r'invoice[\s]*no[\.:]?\s*([A-Z0-9\-/]+)',
                    r'bill[\s]*no[\.:]?\s*([A-Z0-9\-/]+)',
                ]
                for pattern in invoice_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        metadata["invoice_number"] = match.group(1).strip()
                        break
                
                # Extract date
                date_patterns = [
                    r'(?:invoice|bill)[\s]*date[\.:]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                    r'date[\.:]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        metadata["invoice_date"] = match.group(1).strip()
                        break
                
                # Extract GSTIN
                gstin_pattern = r'GSTIN[\.:]?\s*([0-9A-Z]{15})'
                match = re.search(gstin_pattern, text, re.IGNORECASE)
                if match:
                    metadata["gstin"] = match.group(1).strip()
                
                # Extract vendor name (look for common patterns)
                vendor_patterns = [
                    r'(?:from|vendor|supplier|seller)[\s]*:?\s*([A-Z][A-Za-z\s&]+)',
                    r'^([A-Z][A-Za-z\s&]{3,30})\s*(?:GSTIN|Address|Invoice)',
                ]
                for pattern in vendor_patterns:
                    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                    if match:
                        vendor = match.group(1).strip()
                        if len(vendor) > 3 and len(vendor) < 50:
                            metadata["vendor_name"] = vendor
                            break
            
            except Exception as e:
                logger.debug(f"Could not extract metadata from PDF: {e}")
    
    except Exception as e:
        logger.debug(f"Error extracting document metadata: {e}")
    
    return metadata


def generate_document_filename(
    file_path: Path,
    classification: dict,
    parser: DocumentParser,
    doc_id: str
) -> str:
    """Generate a meaningful filename based on document content"""
    try:
        metadata = extract_document_metadata(file_path, classification, parser)
    except Exception as e:
        logger.debug(f"Error extracting metadata: {e}")
        metadata = {
            "doc_type": classification.get("doc_type", {}).get("doc_type", "document"),
            "period": classification.get("category", {}).get("period", {}).get("period") if classification.get("category", {}).get("period") else None,
        }
    
    file_ext = file_path.suffix.lower() or ".pdf"  # Default to .pdf if no extension
    doc_type = sanitize_filename(metadata.get("doc_type", "document"), 20)
    period = metadata.get("period")
    
    # Build filename parts
    parts = []
    
    # Add document type
    parts.append(doc_type)
    
    # Add period if available
    if period:
        period_clean = period.replace("-", "_")
        parts.append(period_clean)
    
    # Add invoice number if available
    if metadata.get("invoice_number"):
        inv_num = sanitize_filename(str(metadata["invoice_number"]), 30)
        if inv_num and inv_num != "unknown":
            parts.append(inv_num)
    
    # Add date if available (and no invoice number)
    elif metadata.get("invoice_date"):
        date_str = sanitize_filename(str(metadata["invoice_date"]), 20)
        if date_str:
            parts.append(date_str)
    
    # Add vendor name if available (shortened)
    if metadata.get("vendor_name"):
        vendor = sanitize_filename(str(metadata["vendor_name"]), 25)
        # Take first word or first 25 chars
        vendor_words = vendor.split("_")
        if vendor_words and vendor_words[0]:
            vendor = vendor_words[0][:25]
            if vendor:
                parts.append(vendor)
    
    # Add GSTIN last 4 digits if available
    if metadata.get("gstin") and len(str(metadata["gstin"])) >= 4:
        parts.append(str(metadata["gstin"])[-4:])
    
    # If we have meaningful parts, use them
    if len(parts) > 1:  # More than just doc_type
        filename = "_".join(parts)
        # Ensure it's not too long (leave room for extension and potential counter)
        max_length = 180
        if len(filename) > max_length:
            filename = filename[:max_length]
        return f"{filename}{file_ext}"
    
    # Fallback: use doc_type, period, and short UUID
    if period:
        return f"{doc_type}_{period.replace('-', '_')}_{doc_id[:8]}{file_ext}"
    
    # Last resort: doc_type and short UUID
    return f"{doc_type}_{doc_id[:8]}{file_ext}"


class DocumentResponse(BaseModel):
    id: str
    client_id: str
    period: str
    doc_type: str
    category: str
    status: str
    upload_date: str
    name: Optional[str] = None
    metadata: Optional[dict] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


# Global instances (would be better with dependency injection)
_processing_queues: dict = {}


async def process_document_task(task: ProcessingTask) -> dict:
    """Process a document task: OCR → Parse → Chunk → Embeddings → Index with retry logic"""
    document_id = task.metadata.get("document_id")
    client_id = task.client_id
    file_path = task.file_path
    
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    db_path = workspace_manager.get_client_database_path(client_id)
    db_manager = DatabaseManager(str(db_path))
    
    max_retries = 3
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            # Update status to processing
            await db_manager.execute(
                "UPDATE documents SET status = ? WHERE id = ?",
                ("processing", document_id)
            )
            
            # Initialize services
            ocr_engine = OCREngine()
            parser = DocumentParser()
            embedding_gen = EmbeddingGenerator()
            chunker = DocumentChunker()
            indexer = DocumentIndexer(db_manager, embedding_gen, chunker)
            
            # Determine file type
            file_ext = file_path.suffix.lower().lstrip('.')
            is_image = file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']
            is_pdf = file_ext == 'pdf'
            
            # Step 1: OCR (if needed for images or scanned PDFs)
            print(f"[PROCESSING STEP] Starting document processing for document_id: {document_id}")
            print(f"[PROCESSING STEP] File type: {file_ext}, File path: {file_path}")
            
            text = ""
            if is_image:
                print(f"[PROCESSING STEP] Step 1: Running OCR on image")
                logger.info(f"Running OCR on image: {file_path}")
                ocr_result = await asyncio.to_thread(ocr_engine.process_file, file_path)
                text = ocr_result.get("text", "")
                print(f"[PROCESSING STEP] OCR completed. Extracted text length: {len(text)} characters")
            elif is_pdf:
                # Try to extract text first
                text = ""
                try:
                    print(f"[PROCESSING STEP] Step 1: Parsing PDF")
                    # Try text extraction specifically first
                    from services.parser import PDFParser
                    text = await asyncio.to_thread(PDFParser.extract_text, file_path)
                except Exception as e:
                    logger.debug(f"Error extracting text from PDF: {e}")
                    text = ""
                
                # If no text extracted, try OCR
                if not text or len(text.strip()) < 50:
                    print(f"[PROCESSING STEP] PDF has little/no text, running OCR")
                    logger.info(f"PDF has little/no text, running OCR: {file_path}")
                    try:
                        ocr_result = await asyncio.to_thread(ocr_engine.process_file, file_path)
                        text = ocr_result.get("text", "")
                        print(f"[PROCESSING STEP] OCR completed. Extracted text length: {len(text)} characters")
                    except Exception as ocr_error:
                        logger.error(f"Error during OCR: {ocr_error}")
                        print(f"[PROCESSING STEP] OCR failed: {ocr_error}")
                else:
                    print(f"[PROCESSING STEP] PDF parsing completed. Extracted text length: {len(text)} characters")
            else:
                # For Excel and other files, parse and convert to text
                print(f"[PROCESSING STEP] Step 1: Parsing file (Excel/other)")
                parsed = await asyncio.to_thread(parser.parse, file_path)
                
                # Convert parsed data to text
                text_parts = []
                if "text" in parsed:
                    text_parts.append(parsed["text"])
                
                if "records" in parsed and parsed["records"]:
                    # Convert records to text representation
                    for record in parsed["records"][:100]:  # Limit to first 100 records
                        record_text = " | ".join([f"{k}: {v}" for k, v in record.items() if not k.startswith("_")])
                        text_parts.append(record_text)
                
                if "tables" in parsed and parsed["tables"]:
                    for table in parsed["tables"]:
                        if "data" in table:
                            for row in table["data"]:
                                text_parts.append(" | ".join([str(cell) if cell else "" for cell in row]))
                
                text = "\n".join(text_parts)
                print(f"[PROCESSING STEP] File parsing completed. Extracted text length: {len(text)} characters")
            
            if not text or len(text.strip()) < 10:
                raise ValueError(f"No text extracted from document {document_id}")
            
            # Step 2: Index document (chunk, embed, store)
            print(f"[PROCESSING STEP] Step 2: Starting indexing (chunk, embed, store)")
            classification = task.metadata.get("classification", {})
            document_metadata = {
                "classification": classification,
                "file_type": file_ext,
                "file_path": str(file_path)
            }
            
            result = await indexer.index_document(
                document_id=document_id,
                text=text,
                document_metadata=document_metadata
            )
            
            print(f"[PROCESSING STEP] Step 2 completed. Chunks created: {result.get('chunks_created', 0)}")
            
            # Update status to indexed
            await db_manager.execute(
                "UPDATE documents SET status = ? WHERE id = ?",
                ("indexed", document_id)
            )
            
            logger.info(f"Successfully processed document {document_id}: {result.get('chunks_created', 0)} chunks")
            
            return {
                "document_id": document_id,
                "chunks_created": result.get("chunks_created", 0),
                "status": "indexed"
            }
            
        except Exception as e:
            retry_count += 1
            last_error = e
            logger.warning(f"Error processing document {document_id} (attempt {retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                # Wait before retrying (exponential backoff)
                await asyncio.sleep(2 ** retry_count)
                continue
            else:
                # All retries exhausted
                logger.error(f"Failed to process document {document_id} after {max_retries} attempts: {e}", exc_info=True)
                # Update status to failed
                await db_manager.execute(
                    "UPDATE documents SET status = ? WHERE id = ?",
                    ("failed", document_id)
                )
                raise


async def process_pending_documents_batch(client_id: Optional[str] = None) -> dict:
    """
    Process all pending documents in batch mode (non-blocking)
    
    Args:
        client_id: Optional client ID to filter by. If None, processes all clients.
    
    Returns:
        Dictionary with processing stats
    """
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    
    processed_count = 0
    failed_count = 0
    client_ids = []
    
    if client_id:
        client_ids = [client_id]
    else:
        # Get all client directories
        clients_dir = workspace_manager.clients_dir
        if clients_dir.exists():
            client_ids = [d.name for d in clients_dir.iterdir() if d.is_dir()]
    
    for cid in client_ids:
        try:
            db_path = workspace_manager.get_client_database_path(cid)
            db_manager = DatabaseManager(str(db_path))
            
            # Get all pending documents
            pending_docs = await db_manager.fetchall(
                "SELECT id, file_path, metadata FROM documents WHERE status = ?",
                ("pending",)
            )
            
            if not pending_docs:
                continue
            
            # Get or create queue for this client
            queue = get_processing_queue(cid)
            await ensure_queue_started(queue)
            
            # Add all pending documents to queue
            for doc in pending_docs:
                doc_id = doc[0]
                file_path_str = doc[1]
                metadata_json = doc[2] if len(doc) > 2 else None
                
                try:
                    file_path = Path(file_path_str)
                    if not file_path.exists():
                        logger.warning(f"File not found for document {doc_id}: {file_path_str}")
                        await db_manager.execute(
                            "UPDATE documents SET status = ? WHERE id = ?",
                            ("failed", doc_id)
                        )
                        failed_count += 1
                        continue
                    
                    # Parse metadata if available
                    classification = {}
                    if metadata_json:
                        try:
                            classification = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
                        except:
                            pass
                    
                    # Add to queue
                    await queue.add_task(
                        file_path=file_path,
                        client_id=cid,
                        task_type="document_processing",
                        metadata={
                            "document_id": doc_id,
                            "classification": classification
                        }
                    )
                    processed_count += 1
                    logger.info(f"Queued pending document {doc_id} for processing")
                    
                except Exception as e:
                    logger.error(f"Error queuing document {doc_id}: {e}")
                    failed_count += 1
                    try:
                        await db_manager.execute(
                            "UPDATE documents SET status = ? WHERE id = ?",
                            ("failed", doc_id)
                        )
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Error processing pending documents for client {cid}: {e}")
            failed_count += 1
    
    return {
        "queued": processed_count,
        "failed": failed_count,
        "total": processed_count + failed_count
    }


async def ensure_queue_started(queue: ProcessingQueue):
    """Ensure a queue is started"""
    if not queue.is_running:
        await queue.start()


def get_processing_queue(client_id: str) -> ProcessingQueue:
    """Get or create processing queue for a client"""
    if client_id not in _processing_queues:
        queue = ProcessingQueue(max_workers=1)
        queue.set_processor(process_document_task)
        _processing_queues[client_id] = queue
    
    queue = _processing_queues[client_id]
    return queue


@router.post("/documents/upload", response_model=List[DocumentResponse])
async def upload_documents(
    client_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """Upload and process documents"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    
    # Get client directory
    client_dir = workspace_manager.clients_dir / client_id
    if not client_dir.exists():
        raise HTTPException(status_code=404, detail="Client not found")
    
    documents_dir = client_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    
    # Get database manager
    db_path = workspace_manager.get_client_database_path(client_id)
    db_manager = DatabaseManager(str(db_path))
    
    # Initialize services
    classifier = DocumentClassifier()
    ocr_engine = OCREngine()
    parser = DocumentParser()
    embedding_gen = EmbeddingGenerator()
    chunker = DocumentChunker()
    indexer = DocumentIndexer(db_manager, embedding_gen, chunker)
    queue = get_processing_queue(client_id)
    
    uploaded_documents = []
    
    for file in files:
        try:
            # Generate document ID
            doc_id = str(uuid.uuid4())
            
            # Save file temporarily with original name to classify and parse
            temp_file_path = documents_dir / f"temp_{doc_id}_{file.filename}"
            file_hash = hashlib.md5()
            
            content = await file.read()
            file_hash.update(content)
            file_hash_str = file_hash.hexdigest()
            
            with open(temp_file_path, "wb") as f:
                f.write(content)
            
            # Check if file already exists (by hash)
            existing = await db_manager.fetchone(
                "SELECT id FROM documents WHERE file_hash = ?",
                (file_hash_str,)
            )
            
            if existing:
                # File already processed, remove temp file
                temp_file_path.unlink()
                continue
            
            # Classify document
            classification = classifier.classify(temp_file_path)
            
            # Generate meaningful filename
            try:
                meaningful_filename = generate_document_filename(
                    temp_file_path,
                    classification,
                    parser,
                    doc_id
                )
            except Exception as e:
                logger.warning(f"Error generating meaningful filename, using fallback: {e}")
                # Fallback to simple name
                doc_type = classification.get("doc_type", {}).get("doc_type", "document")
                period = classification.get("category", {}).get("period", {}).get("period", "")
                if period:
                    meaningful_filename = f"{doc_type}_{period.replace('-', '_')}_{doc_id[:8]}{temp_file_path.suffix}"
                else:
                    meaningful_filename = f"{doc_type}_{doc_id[:8]}{temp_file_path.suffix}"
            
            # Final file path with meaningful name
            file_path = documents_dir / meaningful_filename
            
            # Handle filename conflicts
            counter = 1
            original_file_path = file_path
            while file_path.exists():
                stem = original_file_path.stem
                file_path = documents_dir / f"{stem}_{counter}{original_file_path.suffix}"
                counter += 1
            
            # Rename temp file to final location
            temp_file_path.rename(file_path)
            
            # Create document record
            doc_type = classification.get("doc_type", {}).get("doc_type", "unknown")
            category_info = classification.get("category", {})
            category = category_info.get("category", "general")
            period_info = category_info.get("period")
            if isinstance(period_info, dict):
                period = period_info.get("period") or datetime.now().strftime("%Y-%m")
            elif isinstance(period_info, str):
                period = period_info
            else:
                period = datetime.now().strftime("%Y-%m")
            
            document_data = {
                "id": doc_id,
                "client_id": client_id,
                "period": period,
                "doc_type": doc_type,
                "category": category,
                "file_path": str(file_path),
                "file_hash": file_hash_str,
                "status": "pending",
                "metadata": json.dumps(classification)
            }
            
            # Insert into database
            await db_manager.execute(
                """INSERT INTO documents 
                   (id, client_id, period, doc_type, category, file_path, file_hash, status, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    document_data["id"],
                    document_data["client_id"],
                    document_data["period"],
                    document_data["doc_type"],
                    document_data["category"],
                    document_data["file_path"],
                    document_data["file_hash"],
                    document_data["status"],
                    document_data["metadata"]
                )
            )
            
            # Ensure queue is started
            await ensure_queue_started(queue)
            
            # Add to processing queue
            await queue.add_task(
                file_path=Path(file_path),
                client_id=client_id,
                task_type="document_processing",
                metadata={
                    "document_id": doc_id,
                    "classification": classification
                }
            )
            
            uploaded_documents.append(DocumentResponse(
                id=doc_id,
                client_id=client_id,
                period=document_data["period"],
                doc_type=document_data["doc_type"],
                category=document_data["category"],
                status=document_data["status"],
                upload_date=datetime.now().isoformat(),
                name=meaningful_filename,
                metadata=classification
            ))
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}: {str(e)}")
    
    return uploaded_documents


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    client_id: str = Query(...),
    doc_type: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List documents for a client"""
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    
    db_path = workspace_manager.get_client_database_path(client_id)
    db_manager = DatabaseManager(str(db_path))
    
    # Build query
    query = "SELECT id, client_id, period, doc_type, category, status, upload_date, file_path, metadata FROM documents WHERE client_id = ?"
    params = [client_id]
    
    if doc_type:
        query += " AND doc_type = ?"
        params.append(doc_type)
    
    if period:
        query += " AND period = ?"
        params.append(period)
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY upload_date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    rows = await db_manager.fetchall(query, tuple(params))
    
    # Get total count
    count_query = "SELECT COUNT(*) FROM documents WHERE client_id = ?"
    count_params = [client_id]
    
    if doc_type:
        count_query += " AND doc_type = ?"
        count_params.append(doc_type)
    
    if period:
        count_query += " AND period = ?"
        count_params.append(period)
    
    if status:
        count_query += " AND status = ?"
        count_params.append(status)
    
    total_row = await db_manager.fetchone(count_query, tuple(count_params))
    total = total_row[0] if total_row else 0
    
    documents = []
    for row in rows:
        file_path = row[7] if len(row) > 7 else None
        filename = Path(file_path).name if file_path else None
        documents.append(DocumentResponse(
            id=row[0],
            client_id=row[1],
            period=row[2],
            doc_type=row[3],
            category=row[4],
            status=row[5],
            upload_date=row[6],
            name=filename,
            metadata=json.loads(row[8]) if len(row) > 8 and row[8] else None
        ))
    
    return DocumentListResponse(documents=documents, total=total)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, client_id: str = Query(...)):
    """Get a specific document"""
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    
    db_path = workspace_manager.get_client_database_path(client_id)
    db_manager = DatabaseManager(str(db_path))
    
    row = await db_manager.fetchone(
        "SELECT id, client_id, period, doc_type, category, status, upload_date, file_path, metadata FROM documents WHERE id = ? AND client_id = ?",
        (document_id, client_id)
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = row[7] if len(row) > 7 else None
    filename = Path(file_path).name if file_path else None
    
    return DocumentResponse(
        id=row[0],
        client_id=row[1],
        period=row[2],
        doc_type=row[3],
        category=row[4],
        status=row[5],
        upload_date=row[6],
        name=filename,
        metadata=json.loads(row[8]) if len(row) > 8 and row[8] else None
    )


@router.get("/documents/{document_id}/file")
async def download_document(document_id: str, client_id: str = Query(...)):
    """Download document file"""
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    
    db_path = workspace_manager.get_client_database_path(client_id)
    db_manager = DatabaseManager(str(db_path))
    
    row = await db_manager.fetchone(
        "SELECT file_path FROM documents WHERE id = ? AND client_id = ?",
        (document_id, client_id)
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    file_path = Path(row[0])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream"
    )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, client_id: str = Query(...)):
    """Delete a document"""
    workspace_path = get_default_workspace_path()
    workspace_manager = WorkspaceManager(workspace_path)
    
    db_path = workspace_manager.get_client_database_path(client_id)
    db_manager = DatabaseManager(str(db_path))
    
    # Get file path before deleting
    row = await db_manager.fetchone(
        "SELECT file_path FROM documents WHERE id = ? AND client_id = ?",
        (document_id, client_id)
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete from database (cascade will delete chunks)
    await db_manager.execute(
        "DELETE FROM documents WHERE id = ? AND client_id = ?",
        (document_id, client_id)
    )
    
    # Delete file
    file_path = Path(row[0])
    if file_path.exists():
        file_path.unlink()
    
    return {"status": "deleted", "document_id": document_id}


@router.post("/documents/process-pending")
async def process_pending_documents(
    client_id: Optional[str] = Query(None)
):
    """Process all pending documents in batch mode (non-blocking)"""
    # Run in background task (non-blocking)
    import asyncio
    asyncio.create_task(process_pending_documents_batch(client_id))
    
    return {
        "status": "started",
        "message": "Processing pending documents in background"
    }

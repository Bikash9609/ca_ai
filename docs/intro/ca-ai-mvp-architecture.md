# CA AI MVP - Complete Engineering Blueprint
## Local-First, Privacy-Preserving Architecture

---

## PART 1: CORE PRINCIPLES & PHILOSOPHY

### Why Local-First Matters for CAs
- **Legal Liability**: Data breaches = audit failures + client compensation
- **Trust**: "Your data never leaves your machine" = immediate credibility
- **Offline Capability**: Work during internet outages (crucial for India)
- **Speed**: No latency, no cold starts
- **Compliance**: No data residency questions

### Cursor Analogy (Critical Understanding)
```
Cursor Model:
├─ Code stays on disk
├─ Only relevant diffs sent to AI
├─ No training on your code
├─ Full user control
└─ Privacy by architecture, not policy

Your CA App Model:
├─ Documents stay in workspace
├─ Only computed summaries sent to AI
├─ No training on client data
├─ Full user control
└─ Same architectural guarantee
```

---

## PART 2: LOCAL WORKSPACE STRUCTURE

### Directory Architecture
```
/ca-ai-workspaces/
├── config/
│   ├── app-settings.json          # App config (no sensitive data)
│   ├── encryption-keys.json       # Local encryption keys (encrypted at rest)
│   └── user-preferences.json      # UI/workflow preferences
│
├── clients/
│   ├── ABC_Pvt_Ltd_GSTIN123/
│   │   ├── metadata.json          # Client master data
│   │   ├── index.db               # SQLite: vectorized docs
│   │   ├── vectors.bin            # Embedding index
│   │   ├── audit_log.json         # All actions logged locally
│   │   │
│   │   ├── 2024-25/
│   │   │   ├── GST/
│   │   │   │   ├── _raw/          # Original uploads (never modified)
│   │   │   │   │   ├── sales/
│   │   │   │   │   ├── purchases/
│   │   │   │   │   └── 2b/
│   │   │   │   │
│   │   │   │   ├── _processed/    # OCR + extracted data
│   │   │   │   │   ├── sales.json
│   │   │   │   │   ├── purchases.json
│   │   │   │   │   └── 2b.json
│   │   │   │   │
│   │   │   │   ├── working_papers/
│   │   │   │   │   ├── july/
│   │   │   │   │   │   ├── invoice_register.xlsx
│   │   │   │   │   │   ├── reconciliation.json
│   │   │   │   │   │   └── draft_gstr1.json
│   │   │   │   │   └── august/
│   │   │   │   │
│   │   │   │   └── drafts/
│   │   │   │       └── july_gstr_draft.json
│   │   │   │
│   │   │   ├── IT/
│   │   │   │   ├── _raw/
│   │   │   │   │   ├── bank_statements/
│   │   │   │   │   ├── investment_proofs/
│   │   │   │   │   └── tds_certificates/
│   │   │   │   └── _processed/
│   │   │   │
│   │   │   └── General/
│   │   │       ├── invoices/
│   │   │       ├── agreements/
│   │   │       └── communications/
│   │   │
│   │   └── 2023-24/            # Previous year (archived but accessible)
│   │
│   └── XYZ_Solutions_GSTIN456/
│       └── [similar structure]
│
└── temp/
    ├── uploads/                 # Processing queue
    ├── exports/                 # Generated files
    └── cache/                   # Embeddings cache (regenerable)
```

### Key Rules
1. **Raw files never modified** (`_raw/`)
2. **Processed data is regenerable** (can delete `_processed/` anytime)
3. **User can delete entire client instantly** (no cloud dependency)
4. **Audit logs are immutable** (append-only)
5. **No background uploads** (zero network surprises)

---

## PART 3: DOCUMENT INGESTION PIPELINE (LOCAL)

### Step 1: Detection & Classification

```python
# /backend/services/document_classifier.py

class DocumentClassifier:
    """
    Classify uploaded documents without ML overhead.
    Uses file signatures, metadata, content sniffing.
    """
    
    def classify(self, file_path: str) -> dict:
        """
        Returns:
        {
            "type": "invoice" | "statement" | "notice" | "certificate",
            "category": "sales" | "purchase" | "gst" | "it",
            "period": "2024-07",
            "confidence": 0.95,
            "needs_ocr": True,
            "file_format": "pdf" | "image" | "excel"
        }
        """
        
        # 1. File signature check
        file_ext = self._get_extension(file_path)
        magic_bytes = self._read_magic_bytes(file_path)
        
        # 2. Metadata extraction
        creation_date = self._extract_date(file_path)
        
        # 3. Content sniffing (header text)
        text_preview = self._extract_preview(file_path)
        
        # 4. Classification rules (deterministic)
        classification = {
            "type": self._detect_type(text_preview, file_ext),
            "category": self._detect_category(text_preview),
            "period": self._extract_period(text_preview, creation_date),
            "confidence": self._calculate_confidence(
                text_preview, file_ext, magic_bytes
            ),
            "needs_ocr": file_ext in ['.pdf', '.jpg', '.png'],
            "file_format": self._detect_format(magic_bytes)
        }
        
        return classification
    
    def _detect_type(self, text: str, ext: str) -> str:
        """Rule-based detection"""
        keywords = {
            "invoice": ["invoice", "bill", "tax invoice"],
            "statement": ["statement", "summary", "account"],
            "notice": ["notice", "intimation", "demand"],
            "certificate": ["certificate", "deduction"]
        }
        
        for doc_type, keywords_list in keywords.items():
            if any(kw in text.lower() for kw in keywords_list):
                return doc_type
        return "unknown"
    
    def _detect_category(self, text: str) -> str:
        """Categorize into GST, IT, etc."""
        if "gstr" in text.lower() or "gstin" in text.lower():
            return "gst"
        elif "itr" in text.lower() or "pan" in text.lower():
            return "it"
        elif "invoice" in text.lower():
            return "purchase" if "from:" in text.lower() else "sales"
        return "general"
    
    def _extract_period(self, text: str, date_obj) -> str:
        """Extract financial period"""
        # Try to find explicit period
        import re
        pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).*?(\d{4})'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            month_str, year = match.groups()
            # Convert to financial year format
            return self._to_financial_period(month_str, year)
        
        # Fallback to file date
        if date_obj:
            return self._to_financial_period_from_date(date_obj)
        
        return "unknown"
```

### Step 2: OCR Pipeline (Local)

```python
# /backend/services/ocr_engine.py

from pytesseract import pytesseract
from pdf2image import convert_from_path
import cv2
import numpy as np

class LocalOCREngine:
    """
    On-device OCR using Tesseract/PaddleOCR.
    Zero cloud calls. Works offline.
    """
    
    def __init__(self, ocr_backend="tesseract"):
        self.backend = ocr_backend  # tesseract or paddleocr
        self.cache_dir = "temp/ocr_cache"
        
    def process_document(self, file_path: str) -> dict:
        """
        Full pipeline: preprocess → OCR → post-process
        Returns structured data.
        """
        
        # Step 1: Convert to images if needed
        images = self._to_images(file_path)
        
        # Step 2: Preprocess each image
        processed_images = [
            self._preprocess_image(img) 
            for img in images
        ]
        
        # Step 3: OCR
        ocr_results = []
        for idx, img in enumerate(processed_images):
            result = self._ocr_image(img)
            ocr_results.append({
                "page": idx + 1,
                "text": result["text"],
                "confidence": result["confidence"],
                "tables": result["tables"]
            })
        
        # Step 4: Post-process (structure extraction)
        structured = self._post_process(ocr_results, file_path)
        
        return structured
    
    def _to_images(self, file_path: str) -> list:
        """Convert PDF/image to PIL images"""
        if file_path.endswith('.pdf'):
            return convert_from_path(file_path, dpi=300)
        else:
            return [Image.open(file_path)]
    
    def _preprocess_image(self, image):
        """
        Improve OCR accuracy:
        - Deskew
        - Denoise
        - Enhance contrast
        """
        img = np.array(image)
        
        # 1. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # 2. Denoise
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # 3. Deskew
        coords = np.column_stack(np.where(denoised > 150))
        angle = cv2.minAreaRect(cv2.convexHull(coords))[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 1:
            h, w = denoised.shape
            center = (w // 2, h // 2)
            rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            denoised = cv2.warpAffine(
                denoised, rot_matrix, (w, h),
                flags=cv2.INTER_CUBIC
            )
        
        # 4. Contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        return enhanced
    
    def _ocr_image(self, image_array):
        """Run OCR engine"""
        if self.backend == "tesseract":
            text = pytesseract.image_to_string(image_array)
            confidence = self._estimate_confidence(image_array)
            
            # Table extraction (optional)
            tables = self._extract_tables(image_array)
            
            return {
                "text": text,
                "confidence": confidence,
                "tables": tables
            }
    
    def _extract_tables(self, image_array):
        """
        Detect table regions and extract as structured data.
        Uses line detection + OCR on table cells.
        """
        # Detect horizontal/vertical lines
        # Identify table boundaries
        # Extract cells
        # OCR each cell
        # Return list of tables: [{"headers": [], "rows": []}]
        pass
    
    def _post_process(self, ocr_results: list, original_path: str) -> dict:
        """
        Convert raw OCR to structured invoice/statement format.
        Example: Extract invoice items into JSON table.
        """
        
        combined_text = "\n".join([r["text"] for r in ocr_results])
        
        # Extract structured fields using regex + NLP
        extracted = {
            "document_type": self._detect_doc_type(combined_text),
            "invoice_number": self._extract_invoice_number(combined_text),
            "invoice_date": self._extract_date(combined_text),
            "vendor": self._extract_vendor(combined_text),
            "items": self._extract_items(ocr_results),
            "amounts": self._extract_amounts(combined_text),
            "gst_details": self._extract_gst(combined_text),
            "raw_text": combined_text,
            "confidence": np.mean([r["confidence"] for r in ocr_results])
        }
        
        return extracted
    
    def _extract_invoice_number(self, text: str) -> str:
        import re
        # Pattern: Invoice No, Bill No, Inv#
        pattern = r'(?:invoice|bill|inv)[\s#]*:?[\s]*([A-Z0-9\-/]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else "unknown"
    
    def _extract_items(self, ocr_results: list) -> list:
        """
        Extract line items (HSN, Description, Qty, Rate, Amount).
        This is where table extraction comes in.
        """
        items = []
        # For each detected table in ocr_results
        # Map columns to: HSN | Description | Qty | Rate | Amount | SGST | CGST
        # Return normalized items list
        return items
    
    def _extract_gst(self, text: str) -> dict:
        """Extract GST-relevant fields"""
        import re
        
        gstin_pattern = r'GSTIN[:=]?\s*([0-9A-Z]{15})'
        sgst_pattern = r'SGST[:=]?\s*(?:₹|Rs)?\s*([\d,\.]+)'
        cgst_pattern = r'CGST[:=]?\s*(?:₹|Rs)?\s*([\d,\.]+)'
        igst_pattern = r'IGST[:=]?\s*(?:₹|Rs)?\s*([\d,\.]+)'
        
        return {
            "gstin": re.search(gstin_pattern, text),
            "sgst": float(re.search(sgst_pattern, text).group(1) or 0),
            "cgst": float(re.search(cgst_pattern, text).group(1) or 0),
            "igst": float(re.search(igst_pattern, text).group(1) or 0),
        }
```

### Step 3: Document Parsing (Excel, JSON, etc.)

```python
# /backend/services/document_parser.py

class DocumentParser:
    """Parse structured formats (Excel, CSV, JSON)"""
    
    def parse_excel(self, file_path: str) -> dict:
        """
        Parse GSTR-2B, bank statements, invoice exports, etc.
        Detect schema automatically.
        """
        import pandas as pd
        
        # Try all sheets
        xls = pd.ExcelFile(file_path)
        
        parsed_sheets = {}
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Auto-detect what this sheet is
            sheet_type = self._detect_sheet_type(df)
            
            # Normalize schema
            normalized = self._normalize_schema(df, sheet_type)
            
            parsed_sheets[sheet_name] = {
                "type": sheet_type,
                "data": normalized.to_dict('records'),
                "columns": list(normalized.columns)
            }
        
        return {
            "file_path": file_path,
            "sheets": parsed_sheets,
            "detected_type": "gstr2b" | "bank_statement" | "invoice_register"
        }
    
    def _detect_sheet_type(self, df: pd.DataFrame) -> str:
        """
        Look for characteristic columns:
        - GSTR-2B: "GSTIN", "Inv No", "Inv Date", "Taxable Value"
        - Bank statement: "Date", "Debit", "Credit", "Balance"
        - Invoice register: "Invoice", "Date", "Amount", "Party"
        """
        columns_lower = [col.lower() for col in df.columns]
        
        if any(x in columns_lower for x in ["gstin", "inv no", "inv date"]):
            return "gstr2b"
        elif any(x in columns_lower for x in ["date", "debit", "credit", "balance"]):
            return "bank_statement"
        elif any(x in columns_lower for x in ["invoice", "party", "amount"]):
            return "invoice_register"
        
        return "unknown"
    
    def _normalize_schema(self, df: pd.DataFrame, sheet_type: str) -> pd.DataFrame:
        """
        Standardize column names and data types.
        So downstream processing sees consistent schema.
        """
        
        if sheet_type == "gstr2b":
            # Expected: GSTIN, Inv No, Inv Date, Taxable Value, SGST, CGST, IGST
            mapping = {
                r'(?:gstin|gin)': 'gstin',
                r'(?:inv|invoice).*no': 'invoice_number',
                r'(?:inv|invoice).*date': 'invoice_date',
                r'(?:taxable|taxablevalue|amount)': 'taxable_value',
                r'sgst': 'sgst',
                r'cgst': 'cgst',
                r'igst': 'igst'
            }
            
            df.columns = [self._map_column_name(col, mapping) for col in df.columns]
        
        # Standardize data types
        df['taxable_value'] = pd.to_numeric(df['taxable_value'], errors='coerce')
        df['sgst'] = pd.to_numeric(df['sgst'], errors='coerce').fillna(0)
        df['cgst'] = pd.to_numeric(df['cgst'], errors='coerce').fillna(0)
        df['igst'] = pd.to_numeric(df['igst'], errors='coerce').fillna(0)
        
        return df
```

---

## PART 4: LOCAL INDEXING & SEARCH

### Vectorization Strategy (Critical)

```python
# /backend/services/document_indexer.py

class DocumentIndexer:
    """
    Create searchable, queryable index of all documents.
    ALL processing is local.
    """
    
    def __init__(self, workspace_path: str):
        self.workspace = workspace_path
        self.db = self._init_sqlite()
        self.embeddings = self._init_embeddings()
    
    def _init_sqlite(self):
        """
        Create local SQLite DB with FTS5 (full-text search).
        Plus vector extension for semantic search.
        """
        import sqlite3
        from sqlite_vec import load
        
        conn = sqlite3.connect(f"{self.workspace}/index.db")
        load(conn)
        
        # Create tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                client_id TEXT,
                period TEXT,
                doc_type TEXT,
                category TEXT,
                file_path TEXT,
                upload_date TIMESTAMP,
                file_hash TEXT UNIQUE,
                status TEXT DEFAULT 'indexed'
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                chunk_index INT,
                text TEXT,
                embedding BLOB,
                metadata JSON,
                FOREIGN KEY(document_id) REFERENCES documents(id)
            )
        """)
        
        conn.execute("""
            CREATE VIRTUAL TABLE document_fts USING fts5(
                text,
                metadata UNINDEXED,
                content=document_chunks,
                content_rowid=rowid
            )
        """)
        
        return conn
    
    def _init_embeddings(self):
        """
        Local embeddings using sentence-transformers.
        Runs on CPU. No cloud calls.
        
        Model: sentence-transformers/all-MiniLM-L6-v2
        Reason: Fast, small, good for Indian financial terms
        """
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer(
            'sentence-transformers/all-MiniLM-L6-v2',
            cache_folder=f"{self.workspace}/models"
        )
        return model
    
    def index_document(self, document: dict) -> None:
        """
        Index a processed document.
        Creates chunks and embeddings.
        """
        doc_id = document['id']
        
        # Step 1: Create chunks (250 tokens, 50 token overlap)
        chunks = self._chunk_document(document)
        
        # Step 2: Generate embeddings for each chunk
        chunk_texts = [chunk['text'] for chunk in chunks]
        embeddings = self.embeddings.encode(chunk_texts, show_progress_bar=False)
        
        # Step 3: Store in SQLite
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{doc_id}_chunk_{idx}"
            
            self.db.execute(
                """
                INSERT INTO document_chunks 
                (id, document_id, chunk_index, text, embedding, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    doc_id,
                    idx,
                    chunk['text'],
                    embedding.tobytes(),  # Store as BLOB
                    json.dumps(chunk['metadata'])
                )
            )
        
        self.db.commit()
    
    def _chunk_document(self, document: dict) -> list:
        """
        Split document into overlapping chunks.
        Preserve context.
        """
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=250,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " "]
        )
        
        text = document.get('raw_text', '')
        
        chunks_list = splitter.split_text(text)
        
        return [
            {
                'text': chunk,
                'metadata': {
                    'source': document['file_path'],
                    'doc_type': document['type'],
                    'period': document['period'],
                    'invoice_number': document.get('invoice_number'),
                    'vendor': document.get('vendor')
                }
            }
            for chunk in chunks_list
        ]
    
    def semantic_search(self, query: str, limit: int = 5) -> list:
        """
        Find relevant documents using semantic search.
        Used by the AI to know what to look at.
        """
        
        # Encode query
        query_embedding = self.embeddings.encode(query, convert_to_tensor=True)
        
        # Search in vector DB
        results = self.db.execute("""
            SELECT 
                document_chunks.id,
                documents.file_path,
                documents.doc_type,
                document_chunks.text,
                vec_distance_cosine(embedding, ?) as distance
            FROM document_chunks
            JOIN documents ON document_chunks.document_id = documents.id
            ORDER BY distance ASC
            LIMIT ?
        """, (query_embedding.tobytes(), limit)).fetchall()
        
        return [
            {
                'chunk_id': r[0],
                'source': r[1],
                'type': r[2],
                'text': r[3],
                'relevance': 1 - r[4]  # Convert distance to similarity
            }
            for r in results
        ]
    
    def full_text_search(self, query: str, limit: int = 10) -> list:
        """
        Fast keyword-based search (fallback to semantic search).
        """
        
        results = self.db.execute("""
            SELECT 
                document_chunks.id,
                documents.file_path,
                documents.doc_type,
                document_chunks.text
            FROM document_fts
            JOIN document_chunks ON document_fts.rowid = document_chunks.rowid
            JOIN documents ON document_chunks.document_id = documents.id
            WHERE document_fts MATCH ?
            LIMIT ?
        """, (query, limit)).fetchall()
        
        return [
            {
                'chunk_id': r[0],
                'source': r[1],
                'type': r[2],
                'text': r[3]
            }
            for r in results
        ]
```

---

## PART 5: CONTEXT FIREWALL (Most Critical)

### The Mental Model
```
BAD (what you DON'T want):
User → Files → LLM → Training/Storage
Risk: Privacy leak, data leak, model contamination

GOOD (Cursor-style):
User → App → Tools → LLM → App → User
LLM sees only: summaries, questions, computed results
LLM never touches: raw files, personal data
```

### Implementation

```python
# /backend/services/context_firewall.py

class ContextFirewall:
    """
    CRITICAL: LLM cannot bypass this.
    Everything LLM does flows through here.
    """
    
    def __init__(self, workspace: str, indexer: DocumentIndexer):
        self.workspace = workspace
        self.indexer = indexer
        self.audit_log = AuditLog(workspace)
        
        # Define what LLM is allowed to do
        self.allowed_tools = {
            "search_documents": self.search_documents,
            "get_invoice": self.get_invoice,
            "get_summary": self.get_summary,
            "get_reconciliation": self.get_reconciliation,
            "explain_rule": self.explain_rule,
            "ask_for_documents": self.ask_for_documents
        }
    
    def validate_llm_request(self, request: dict) -> bool:
        """
        Before LLM gets ANY access, check:
        1. Is the tool in allowed_tools?
        2. Are parameters valid?
        3. No path traversal / file access tricks?
        """
        tool = request.get('tool')
        params = request.get('params', {})
        
        # Check tool whitelist
        if tool not in self.allowed_tools:
            raise PermissionError(f"Tool '{tool}' not allowed")
        
        # Check parameter validation
        if not self._validate_params(tool, params):
            raise ValueError(f"Invalid parameters for {tool}")
        
        # No raw file paths
        if 'file_path' in params or 'path' in params:
            raise PermissionError("Cannot access files directly")
        
        # Log the request
        self.audit_log.log_tool_request(tool, params)
        
        return True
    
    def execute_tool(self, tool: str, params: dict) -> dict:
        """
        Execute tool through firewall.
        """
        self.validate_llm_request({'tool': tool, 'params': params})
        
        tool_fn = self.allowed_tools[tool]
        result = tool_fn(**params)
        
        # Log execution
        self.audit_log.log_tool_result(tool, params, result)
        
        return result
    
    # ALLOWED TOOLS (LLM can only call these)
    
    def search_documents(self, query: str, doc_type: str = None, period: str = None, limit: int = 5) -> dict:
        """
        LLM can ask: "Find all vendor invoices for July"
        Returns: Summaries, not raw files.
        """
        
        # Build search query
        if doc_type and period:
            semantic_results = self.indexer.semantic_search(
                query=query,
                limit=limit
            )
            
            # Filter by doc_type, period
            filtered = [
                r for r in semantic_results
                if r['type'] == doc_type  # Implement filtering
            ]
        else:
            filtered = self.indexer.semantic_search(query, limit)
        
        # Return SUMMARIES, not raw text
        return {
            "query": query,
            "count": len(filtered),
            "results": [
                {
                    "source": r['source'],
                    "type": r['type'],
                    "relevance": r['relevance'],
                    "preview": r['text'][:200] + "..."  # Truncate
                }
                for r in filtered
            ]
        }
    
    def get_invoice(self, invoice_number: str, vendor_name: str = None) -> dict:
        """
        Get specific invoice as structured data.
        Extracted fields, not raw PDF.
        """
        
        # Search by invoice number
        query = f"invoice {invoice_number}"
        results = self.indexer.semantic_search(query, limit=1)
        
        if not results:
            return {"error": f"Invoice {invoice_number} not found"}
        
        # Load from _processed/ folder (never raw)
        # Example: _processed/sales.json
        processed_data = self._load_processed_data(results[0]['source'])
        
        # Find matching invoice
        invoice = next(
            (inv for inv in processed_data if inv['invoice_number'] == invoice_number),
            None
        )
        
        if not invoice:
            return {"error": "Invoice not found"}
        
        # Return structured data (no raw file access)
        return {
            "invoice_number": invoice['invoice_number'],
            "date": invoice['date'],
            "vendor": invoice['vendor'],
            "items": invoice['items'],
            "taxable_value": invoice['taxable_value'],
            "gst_components": {
                "sgst": invoice.get('sgst', 0),
                "cgst": invoice.get('cgst', 0),
                "igst": invoice.get('igst', 0)
            }
        }
    
    def get_summary(self, summary_type: str, period: str, category: str = None) -> dict:
        """
        LLM asks for summaries.
        Returns computed aggregates, not raw data.
        
        Example: "Give me total sales for July"
        """
        
        if summary_type not in ["sales", "purchases", "gst_summary", "itc_summary"]:
            raise ValueError("Invalid summary_type")
        
        # Load all processed documents for this period
        processed = self._load_period_data(period, category)
        
        if summary_type == "sales":
            return {
                "total_sales": sum(inv['taxable_value'] for inv in processed if inv['type'] == 'sales'),
                "invoice_count": len([inv for inv in processed if inv['type'] == 'sales']),
                "top_customers": self._get_top_customers(processed),
                "by_state": self._get_sales_by_state(processed)
            }
        
        elif summary_type == "gst_summary":
            return {
                "sgst": sum(inv.get('sgst', 0) for inv in processed),
                "cgst": sum(inv.get('cgst', 0) for inv in processed),
                "igst": sum(inv.get('igst', 0) for inv in processed),
                "total_gst": sum(
                    inv.get('sgst', 0) + inv.get('cgst', 0) + inv.get('igst', 0)
                    for inv in processed
                )
            }
        
        # More types...
    
    def get_reconciliation(self, source1: str, source2: str, period: str) -> dict:
        """
        Compare two data sources (e.g., books vs GSTR-2B).
        Returns differences, not raw data.
        """
        
        books = self._load_period_data(period, source1)
        gstr2b = self._load_period_data(period, source2)
        
        matches = self._match_invoices(books, gstr2b)
        
        return {
            "matched": len(matches['matched']),
            "books_only": len(matches['books_only']),
            "gstr2b_only": len(matches['gstr2b_only']),
            "mismatches": matches['mismatches'],
            "differences": {
                "missing_in_books": [inv['invoice_number'] for inv in matches['gstr2b_only']],
                "missing_in_gstr2b": [inv['invoice_number'] for inv in matches['books_only']],
                "amount_differences": matches['amount_diffs']
            }
        }
    
    def explain_rule(self, rule_type: str, scenario: dict) -> dict:
        """
        LLM can ask: "Explain ITC blocking rule"
        Returns: Rule text + applicability, not raw laws.
        """
        
        rules_db = {
            "itc_blocking_36_4": {
                "rule": "Rule 36(4)",
                "summary": "ITC blocked if vendor hasn't filed GSTR-1",
                "applicability": "GST",
                "year_from": 2017,
                "conditions": [
                    "Vendor GSTIN not found in GSTR-1",
                    "Vendor filed for period but no matching invoice"
                ]
            },
            # More rules...
        }
        
        if rule_type not in rules_db:
            return {"error": f"Rule {rule_type} not found"}
        
        rule = rules_db[rule_type]
        
        # Check if rule applies to scenario
        applies = self._check_applicability(rule, scenario)
        
        return {
            "rule": rule['rule'],
            "summary": rule['summary'],
            "applies_to_scenario": applies,
            "reason": self._explain_applicability(rule, scenario) if applies else None
        }
    
    def ask_for_documents(self, doc_types: list) -> dict:
        """
        LLM can ask user for more documents.
        Returns checklist, not access to disk.
        """
        
        required = {
            "sales_invoices": "Upload all sales invoices",
            "purchase_invoices": "Upload all purchase invoices",
            "gstr2b": "Download and upload GSTR-2B from GST portal",
            "bank_statements": "Upload bank statements for reconciliation"
        }
        
        missing = []
        for dt in doc_types:
            if dt not in required:
                continue
            
            # Check if we have documents of this type
            if not self._has_documents(dt):
                missing.append({
                    "type": dt,
                    "description": required[dt],
                    "count": 0,
                    "status": "MISSING"
                })
        
        return {
            "needed": doc_types,
            "missing": missing,
            "next_step": "Upload documents to continue"
        }
    
    # FORBIDDEN (LLM can NEVER do these)
    
    def _forbidden_file_access(self):
        """These are BLOCKED"""
        # NO: os.listdir()
        # NO: open(file_path)
        # NO: subprocess calls
        # NO: Database direct access
        # NO: File modification
        # NO: Directory traversal
        # NO: Cloud uploads
        pass
```

---

## PART 6: DETERMINISTIC RULE ENGINE (Non-AI)

### GST Rules Logic

```python
# /backend/rules/gst_rules.py

class GSTRulesEngine:
    """
    Deterministic rules for GST compliance.
    NOT using AI — pure logic.
    
    This is where trust comes from.
    """
    
    def __init__(self):
        self.rules = {}
        self._load_rules()
    
    def _load_rules(self):
        """
        Load from authoritative sources.
        Cite every rule.
        """
        self.rules = {
            "itc_36_4": {
                "name": "ITC Blocking - Non-filing of GSTR-1",
                "rule": "Rule 36(4), GST Rules 2017",
                "citation": "Circular No. 163/19/2022-GST, dated 01.03.2022",
                "logic": self._itc_36_4_logic
            },
            "itc_42": {
                "name": "ITC Reversal on Supply to Unregistered",
                "rule": "Rule 42, GST Rules 2017",
                "citation": "Section 18(4), CGST Act 2017",
                "logic": self._itc_42_logic
            },
            "blocked_credits": {
                "name": "Blocked Credits under GST",
                "rule": "Section 17(5), CGST Act 2017",
                "citation": "Multiple circulars",
                "logic": self._blocked_credits_logic
            }
        }
    
    def evaluate_itc_eligibility(self, invoice: dict, 2b_data: dict) -> dict:
        """
        Determine if invoice is eligible for ITC.
        Returns: {eligible: bool, reason: str, rule: str, amount: float}
        """
        
        # Check Rule 36(4) — vendor in GSTR-2B?
        vendor_in_2b = self._check_vendor_in_2b(
            invoice['vendor_gstin'],
            2b_data
        )
        
        if not vendor_in_2b:
            return {
                "eligible": False,
                "reason": "Vendor not found in GSTR-2B",
                "rule": "Rule 36(4)",
                "itc_blocked": invoice['gst_amount'],
                "action": "Block ITC and defer credit"
            }
        
        # Check Rule 42 — is this a blocked supply?
        if self._is_blocked_supply(invoice):
            return {
                "eligible": False,
                "reason": "Supply to unregistered person",
                "rule": "Rule 42",
                "itc_blocked": invoice['gst_amount'],
                "action": "Reverse ITC"
            }
        
        # Check Section 17(5) — common blocked items
        if self._is_blocked_item(invoice):
            return {
                "eligible": False,
                "reason": "Blocked category (e.g., liquor, petrol)",
                "rule": "Section 17(5)",
                "itc_blocked": invoice['gst_amount'],
                "action": "Disallow ITC"
            }
        
        # Check invoice matching
        matched_in_2b = self._find_matching_invoice(invoice, 2b_data)
        
        if not matched_in_2b:
            return {
                "eligible": "PENDING",
                "reason": "Invoice not matched in GSTR-2B yet (may be early filing)",
                "rule": "Pending verification",
                "itc_amount": invoice['gst_amount'],
                "action": "Allow tentatively, review before filing"
            }
        
        # Amount matching
        amount_match = self._check_amount_match(invoice, matched_in_2b)
        
        if not amount_match['match']:
            return {
                "eligible": False,
                "reason": f"Amount mismatch: {amount_match['difference']}",
                "rule": "Amount verification",
                "itc_allowed": amount_match['safe_amount'],
                "action": "Allow partial ITC, investigate difference"
            }
        
        # All checks passed
        return {
            "eligible": True,
            "reason": "All eligibility criteria met",
            "rule": "GST Act",
            "itc_amount": invoice['gst_amount'],
            "action": "Allow full ITC"
        }
    
    def _check_vendor_in_2b(self, vendor_gstin: str, 2b_data: dict) -> bool:
        """Check if vendor's GSTIN appears in GSTR-2B"""
        vendor_gstins = [inv['vendor_gstin'] for inv in 2b_data['invoices']]
        return vendor_gstin in vendor_gstins
    
    def _is_blocked_supply(self, invoice: dict) -> bool:
        """Check if recipient is unregistered (Rule 42)"""
        # If we have recipient GSTIN info
        if not invoice.get('recipient_gstin'):
            # Supply to unregistered
            return True
        return False
    
    def _is_blocked_item(self, invoice: dict) -> bool:
        """Check Section 17(5) blocked categories"""
        blocked_categories = [
            "liquor",
            "petroleum",
            "motor_vehicles",
            "health_insurance"  # For some scenarios
        ]
        
        item_hsn = invoice.get('hsn_code', '')
        item_description = invoice.get('description', '').lower()
        
        for blocked in blocked_categories:
            if blocked in item_description:
                return True
        
        # Check HSN codes (28xx-30xx for liquor, etc.)
        if item_hsn.startswith('2'):
            return True
        
        return False
    
    def _find_matching_invoice(self, invoice: dict, 2b_data: dict) -> dict:
        """Find matching invoice in GSTR-2B"""
        for inv_2b in 2b_data['invoices']:
            if (inv_2b['vendor_gstin'] == invoice['vendor_gstin'] and
                inv_2b['invoice_number'] == invoice['invoice_number'] and
                abs(inv_2b['date'] - invoice['date']).days < 5):
                return inv_2b
        return None
    
    def _check_amount_match(self, invoice: dict, 2b_invoice: dict) -> dict:
        """Check if amounts match within tolerance"""
        tolerance = 0.01  # 1% variance allowed
        
        inv_amount = invoice['taxable_value']
        b2b_amount = 2b_invoice['taxable_value']
        
        diff_pct = abs(inv_amount - b2b_amount) / inv_amount
        
        if diff_pct <= tolerance:
            return {"match": True, "difference": 0, "safe_amount": invoice['gst_amount']}
        
        # Allow partial ITC for the matched amount
        safe_amount = b2b_amount * (invoice['gst_amount'] / inv_amount)
        
        return {
            "match": False,
            "difference": inv_amount - b2b_amount,
            "safe_amount": safe_amount
        }
    
    def generate_working_paper(self, invoices: list, 2b_data: dict, period: str) -> dict:
        """
        Generate full ITC reconciliation working paper.
        Shows logic for every line.
        """
        
        analysis = {
            "period": period,
            "total_invoices": len(invoices),
            "results": [],
            "summary": {}
        }
        
        total_claimed = 0
        total_allowed = 0
        total_blocked = 0
        
        for invoice in invoices:
            result = self.evaluate_itc_eligibility(invoice, 2b_data)
            
            analysis['results'].append({
                "invoice_number": invoice['invoice_number'],
                "vendor": invoice['vendor'],
                "amount": invoice['gst_amount'],
                **result
            })
            
            total_claimed += invoice['gst_amount']
            
            if result['eligible'] == True:
                total_allowed += result['itc_amount']
            else:
                total_blocked += result['itc_blocked']
        
        analysis['summary'] = {
            "total_claimed": total_claimed,
            "total_allowed": total_allowed,
            "total_blocked": total_blocked,
            "percentage_allowed": (total_allowed / total_claimed * 100) if total_claimed > 0 else 0
        }
        
        return analysis
```

---

## PART 7: LLM REASONING LAYER (Lightweight)

### What the LLM Does (and Doesn't Do)

```python
# /backend/services/llm_reasoner.py

from anthropic import Anthropic

class LLMReasoner:
    """
    LLM for explanation and reasoning.
    NOT for computation, NOT for decisions.
    
    Key: LLM sees SUMMARIES, not raw data.
    """
    
    def __init__(self, firewall: ContextFirewall, rules_engine: GSTRulesEngine):
        self.firewall = firewall
        self.rules = rules_engine
        self.client = Anthropic()
        self.conversation_history = []
        
        # System prompt is CRITICAL
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """
        System prompt defines boundaries.
        This is where trust comes from.
        """
        
        return """
You are a CA's AI assistant for GST compliance and financial analysis.

YOUR ROLE:
- Explain GST rules and their application
- Draft explanatory notes and notices
- Summarize financial documents
- Highlight risks and inconsistencies
- Ask intelligent follow-up questions
- Never compute, never decide unilaterally

CRITICAL CONSTRAINTS:
1. You CANNOT compute tax or ITC amounts. Use the deterministic engine for that.
2. You CANNOT access files directly. You MUST use tools.
3. You CANNOT make final decisions. CA must approve all actions.
4. You CANNOT see raw file contents. Only processed summaries.
5. You CANNOT modify or delete any data.
6. You CANNOT save documents to cloud or external systems.

TOOLS YOU CAN USE:
- search_documents(query, doc_type, period): Find relevant documents
- get_invoice(invoice_number): Get structured invoice data
- get_summary(type, period): Get computed summaries
- get_reconciliation(source1, source2, period): Compare data sources
- explain_rule(rule_type, scenario): Explain GST rules
- ask_for_documents(doc_types): Request missing documents

EXAMPLES OF WHAT TO DO:
User: "Why is ITC blocked for July?"
You: Use get_summary("itc_summary", "2024-07")
     → See results showing "Rule 36(4)" blocks
     → Explain: "3 vendors haven't filed GSTR-1 yet, so ₹1.82L ITC is blocked."

User: "Draft a notice reply"
You: Use search_documents("notice", "it")
     → Get notice summary
     → Draft explanation citing rules
     → CA reviews and modifies

EXAMPLES OF WHAT NOT TO DO:
❌ "Let me compute the ITC for you" (use rules engine)
❌ "I'll open the file directly" (use tools)
❌ "This should be filed as-is" (CA must approve)
❌ "I'll connect to GST portal" (no integrations)

ALWAYS:
- Cite rules and reasons
- Show your work (which documents you checked)
- Flag assumptions and gaps
- Ask for clarification if ambiguous
- Leave final decision to CA

INDIAN CONTEXT:
- GST effective from July 2017
- ITC rules have evolved with circulars
- State-wise applicability varies
- Compliance changes frequently
- Always cite current rules
"""
    
    def process_user_query(self, query: str, client_id: str, period: str) -> dict:
        """
        User asks a question.
        LLM reasons through it using tools.
        Returns explanation + next steps.
        """
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": query
        })
        
        # Build message with tools
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=self.system_prompt,
            tools=self._get_tool_definitions(),
            messages=self.conversation_history
        )
        
        # Process response
        full_response = {
            "reasoning": "",
            "tool_calls": [],
            "next_steps": []
        }
        
        for content_block in response.content:
            if content_block.type == "text":
                full_response["reasoning"] = content_block.text
            
            elif content_block.type == "tool_use":
                # Execute tool through firewall
                tool_result = self.firewall.execute_tool(
                    content_block.name,
                    content_block.input
                )
                
                full_response["tool_calls"].append({
                    "tool": content_block.name,
                    "input": content_block.input,
                    "result": tool_result
                })
                
                # Feed tool result back to LLM for further reasoning
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                self.conversation_history.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": json.dumps(tool_result)
                        }
                    ]
                })
        
        # Add LLM response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content
        })
        
        return full_response
    
    def _get_tool_definitions(self) -> list:
        """
        Define tools available to LLM.
        These are the ONLY tools it can call.
        """
        
        return [
            {
                "name": "search_documents",
                "description": "Search for documents by keyword or semantic meaning",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "What to search for (e.g., 'vendor invoices', 'GST notices')"
                        },
                        "doc_type": {
                            "type": "string",
                            "enum": ["invoice", "statement", "notice", "certificate"]
                        },
                        "period": {
                            "type": "string",
                            "description": "Financial period (e.g., '2024-07')"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_invoice",
                "description": "Get structured data for a specific invoice",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "invoice_number": {
                            "type": "string"
                        },
                        "vendor_name": {
                            "type": "string",
                            "description": "Optional vendor name for verification"
                        }
                    },
                    "required": ["invoice_number"]
                }
            },
            {
                "name": "get_summary",
                "description": "Get aggregated summary (total sales, GST, etc.)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary_type": {
                            "type": "string",
                            "enum": ["sales", "purchases", "gst_summary", "itc_summary"]
                        },
                        "period": {
                            "type": "string",
                            "description": "Financial period"
                        }
                    },
                    "required": ["summary_type", "period"]
                }
            },
            {
                "name": "get_reconciliation",
                "description": "Compare two data sources (e.g., books vs GSTR-2B)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "source1": {"type": "string"},
                        "source2": {"type": "string"},
                        "period": {"type": "string"}
                    },
                    "required": ["source1", "source2", "period"]
                }
            },
            {
                "name": "explain_rule",
                "description": "Get explanation of a specific GST rule",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "rule_type": {
                            "type": "string",
                            "description": "e.g., 'itc_36_4', 'itc_42', 'blocked_credits'"
                        },
                        "scenario": {
                            "type": "object",
                            "description": "Scenario to evaluate the rule against"
                        }
                    },
                    "required": ["rule_type"]
                }
            },
            {
                "name": "ask_for_documents",
                "description": "Request CA to upload specific documents",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "doc_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Types of documents needed"
                        }
                    },
                    "required": ["doc_types"]
                }
            }
        ]
```

---

## PART 8: FULL DATA FLOW EXAMPLE

### "File GST for July" — Step by Step

```
USER TYPES:
"File GST for Client ABC for July"

┌─────────────────────────────────────────────────────────────┐
│ STEP 1: CHAT UI RECEIVES INPUT                              │
└─────────────────────────────────────────────────────────────┘

Input: "File GST for Client ABC for July"
↓
LLM Prompt: "What does the user want?"
LLM Response: 
  - Task: File GST GSTR-1 and GSTR-3B
  - Client: ABC_Pvt_Ltd
  - Period: July 2024
  - Needs: Sales, Purchases, GSTR-2B


┌─────────────────────────────────────────────────────────────┐
│ STEP 2: DATA DISCOVERY (LLM uses tools)                     │
└─────────────────────────────────────────────────────────────┘

LLM calls: search_documents("sales invoices", period="2024-07")
Firewall allows → Indexer searches → Returns: {count: 245, preview: [...]}

LLM calls: search_documents("purchase invoices", period="2024-07")
Firewall allows → Indexer searches → Returns: {count: 98, preview: [...]}

LLM calls: search_documents("gstr2b july")
Firewall allows → Indexer searches → Returns: {found: Yes}

LLM Response to User:
  "I found:
   ✓ 245 sales invoices
   ✓ 98 purchase invoices
   ✓ GSTR-2B
   Ready to process. Click 'Analyze' to continue."


┌─────────────────────────────────────────────────────────────┐
│ STEP 3: PROCESSING (Non-LLM, deterministic)                 │
└─────────────────────────────────────────────────────────────┘

Backend runs (no LLM involved):
  1. Load all sales invoices from _processed/
  2. Aggregate: Total sales = ₹1,23,45,000
  3. Extract tax: SGST, CGST, IGST
  4. Load GSTR-2B
  5. Match purchases vs GSTR-2B
  6. Evaluate ITC eligibility (Rule 36(4), etc.)
  7. Generate working papers

Results:
  Sales total: ₹1,23,45,000
  Purchases: ₹78,90,000
  ITC Claimed: ₹15,23,400
  ITC Blocked: ₹1,82,300 (Rule 36(4) — 3 vendors not in GSTR-2B)
  ITC Allowed: ₹13,41,100


┌─────────────────────────────────────────────────────────────┐
│ STEP 4: LLM EXPLANATION                                     │
└─────────────────────────────────────────────────────────────┘

LLM calls: get_summary("gst_summary", "2024-07")
Firewall returns: {sgst: 3.5Cr, cgst: 3.5Cr, igst: 2.1Cr, ...}

LLM calls: get_reconciliation("books", "gstr2b", "2024-07")
Firewall returns: {
  matched: 85,
  missing_in_2b: 13,
  amount_differences: [...]
}

LLM generates:
  "GST Summary for July:
   
   Sales: ₹1,23,45,000
   Purchases: ₹78,90,000
   
   GST Liability:
   • SGST: ₹3,50,00,000
   • CGST: ₹3,50,00,000
   • IGST: ₹2,10,00,000
   
   ITC Analysis:
   • Claimed: ₹15,23,400
   • Blocked: ₹1,82,300 (Rule 36(4) — Vendors XYZ, ABC, DEF not filed)
   • Allowed: ₹13,41,100
   
   Risks:
   ⚠ 13 invoices not yet in GSTR-2B (may be approved before filing)
   ⚠ Confirm GSTR-2B finalization date before filing GSTR-3B
   
   Next: Review drafts and approve for filing"


┌─────────────────────────────────────────────────────────────┐
│ STEP 5: CA APPROVAL SCREEN                                  │
└─────────────────────────────────────────────────────────────┘

CA sees:
  ┌──────────────────────────────────┐
  │  GSTR-1 Draft                    │
  ├──────────────────────────────────┤
  │ Sales (B2B): 245 invoices        │
  │            ₹1,23,45,000          │
  │ Total tax:  ₹26,08,450           │
  │                                  │
  │ [✓ Approve] [✗ Reject] [Edit]   │
  └──────────────────────────────────┘
  
  ┌──────────────────────────────────┐
  │  GSTR-3B Draft                   │
  ├──────────────────────────────────┤
  │ Outward Supplies: ₹1,23,45,000   │
  │ Inward Supplies:  ₹78,90,000     │
  │ ITC Claimed:      ₹15,23,400     │
  │ ITC Blocked:      ₹1,82,300      │
  │ Net ITC:          ₹13,41,100     │
  │ Tax Payable:      ₹12,67,350     │
  │                                  │
  │ [✓ Approve] [✗ Reject] [Edit]   │
  └──────────────────────────────────┘

CA clicks: [✓ Approve GSTR-1]
         [✓ Approve GSTR-3B]


┌─────────────────────────────────────────────────────────────┐
│ STEP 6: LOGGING & EXECUTION                                 │
└─────────────────────────────────────────────────────────────┘

Audit log records:
  Time: 2024-08-15 14:32:00
  User: CA_Name
  Action: Approved GSTR-1 & GSTR-3B for ABC Pvt Ltd
  Period: July 2024
  Details: [full JSON]

Execution (user can now file manually):
  - Download GSTR-1 JSON
  - Download GSTR-3B JSON
  - CA uploads to GST portal manually (no auto-filing yet)

All data stays local.
All decisions logged.
All documents preserved.
```

---

## PART 9: TECH STACK & ARCHITECTURE

### Frontend
```
Technology: Electron + React + TailwindCSS
├─ Chat UI (similar to Cursor)
├─ Document upload + progress
├─ Approval dashboard
├─ Review screen (diffs)
└─ Settings (local preferences only)

No: Cloud sync, auto-upload, telemetry
```

### Backend
```
Language: Python 3.11+
Framework: FastAPI (lightweight, async)

Services:
├─ document_classifier.py    # File detection
├─ ocr_engine.py             # Tesseract/PaddleOCR
├─ document_parser.py        # Excel, JSON, CSV
├─ document_indexer.py       # SQLite + embeddings
├─ context_firewall.py       # Access control (CRITICAL)
├─ gst_rules.py              # Deterministic rules
├─ llm_reasoner.py           # Claude integration
└─ audit_log.py              # Immutable logging

Data:
├─ SQLite (index.db)         # Full-text + vector search
├─ Local file system         # Document storage
├─ Vectors (embeddings)      # Sentence-transformers cache
└─ Audit logs               # Append-only JSON

External (with strict controls):
├─ Claude API (via context firewall only)
└─ Sentence-transformers (runs locally)
```

### Privacy Guarantees (Rust-style implementation)

```python
# /backend/core/privacy_guarantee.py

"""
This is the hardest part.
Implement ownership semantics: data stays with user.
"""

class PrivacyGuarantee:
    """
    Principles:
    1. Ownership: User owns all data
    2. Locality: All processing is local
    3. Transparency: User sees everything
    4. Control: User controls what is shared
    5. Deletion: User can delete instantly
    """
    
    # INVARIANT: No data leaves workspace without explicit user action
    # INVARIANT: No background uploads
    # INVARIANT: No AI training on user data
    # INVARIANT: All LLM interactions logged and reviewable
    
    def __init__(self):
        self.workspace = None
        self.encryption_enabled = False
    
    def set_workspace(self, path: str):
        """User chooses where data lives"""
        self.workspace = path
    
    def get_data_location(self) -> str:
        """Transparent: User can see where data is"""
        return self.workspace
    
    def list_all_data(self) -> list:
        """User can see everything stored"""
        import os
        all_files = []
        for root, dirs, files in os.walk(self.workspace):
            for file in files:
                all_files.append(os.path.join(root, file))
        return all_files
    
    def delete_all_data(self) -> bool:
        """User can delete everything instantly"""
        import shutil
        shutil.rmtree(self.workspace)
        return True
    
    def export_data(self, format: str = "original") -> str:
        """User can export data in original format"""
        if format == "original":
            return f"Zip of: {self.workspace}"
        elif format == "portable":
            return "JSON export of processed data"
    
    def audit_all_llm_interactions(self) -> list:
        """User can see every query sent to LLM"""
        # Return all interactions from audit log
        pass
    
    @property
    def data_shared_with_llm(self) -> int:
        """What percentage of data sees LLM?"""
        # Typically < 5%
        # Only summaries, not raw files
        return 3  # 3% (rough estimate)
```

---

## PART 10: DEPLOYMENT & OPERATIONS

### Local Installation

```bash
# Download app (no install required)
ca-ai-app-v0.1.dmg / .exe

# User runs
# Chooses workspace folder (e.g., ~/Documents/CA_Workspace/)
# Offline ready

# Zero cloud dependency
# Works without internet (except LLM calls, which are optional)
```

### Privacy Checklist for Users

```
Before using, CA should verify:

☐ Data location: ~/Documents/ca-workspace/ (or user's choice)
☐ No network calls during processing (check network tab)
☐ Firewall allows: Claude API only (if using cloud LLM)
☐ Encryption: Optional, for paranoid CAs
☐ Audit log accessible: View all LLM queries
☐ Can delete instantly: No cloud holdback
☐ Can export: Download everything

This is Cursor-level privacy.
```

---

## CONCLUSION: Why This Works

```
Current CA Workflow (2024):
├─ Tally for books
├─ Excel for working
├─ ClearTax for GST
├─ ChatGPT + uploads for questions
├─ Manual consolidation
└─ 40+ hours/month per client

Your MVP (with document upload):
├─ One app
├─ Upload documents
├─ AI asks for what's needed
├─ Deterministic rules compute
├─ LLM explains
├─ CA approves
└─ 8-10 hours/month per client

5x productivity boost.
Same privacy as Cursor.
Actually buildable in 6-9 months.
```

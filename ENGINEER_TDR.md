# CA AI MVP - Technical Decision Record (TDR)

## Finalized Architecture & Implementation Plan

**Date:** 2024-12-15
**Status:** Finalized
**Version:** 1.0

---

## EXECUTIVE SUMMARY

This document finalizes all technical decisions for the CA AI MVP - a local-first, privacy-preserving application for Chartered Accountants to manage GST compliance with AI assistance.

**Core Principle:** Documents never leave user's machine. LLM sees only summaries (Cursor-style architecture).

---

## PART 1: FINALIZED TECHNICAL DECISIONS

### 1.1 Architecture Pattern

**Decision:** Local-First with Context Firewall
**Rationale:**

- Privacy is non-negotiable for CA profession
- Offline capability essential for India
- Cursor-style architecture proven and trusted

**Implementation:**

- All processing happens on user's machine
- LLM receives only computed summaries (never raw files)
- Context firewall enforces privacy guarantees
- Rules server for GST knowledge (like Cursor's update system)

### 1.2 Frontend Technology

**Decision:** Tauri 2.0 + React 19 + TypeScript 5.5
**Rationale:**

- Tauri: 5MB vs Electron's 150MB, faster, Rust-based security
- React 19: Latest features, better performance
- TypeScript: Type safety for complex financial logic

**Alternatives Considered:**

- ❌ Electron: Too heavy, slower
- ❌ VSCode Extension: Wrong use case, security concerns
- ❌ Web-only: Needs offline capability

### 1.3 Backend Technology

**Decision:** Python 3.12+ + FastAPI 0.115+
**Rationale:**

- Python: Best ecosystem for OCR, ML, data processing
- FastAPI: Async, high performance, modern
- Pydantic V2: Fast validation, 5-10x faster than V1

**Key Libraries:**

- `uv` (package manager): 10-100x faster than pip
- `aiofiles`: Async file operations
- `asyncio`: Concurrent processing

### 1.4 OCR Engine

**Decision:** PaddleOCR 2.7+ (Primary) + Tesseract (Fallback)
**Rationale:**

- PaddleOCR: Better accuracy for Indian invoices (85-90%)
- Supports Hindi/English mixed text
- Better table extraction
- Tesseract: Fallback for edge cases

### 1.5 Vector Search

**Decision:** SQLite + sqlite-vec extension
**Rationale:**

- No separate vector DB needed
- Single file per client (portable)
- Sufficient for 50k documents
- Can migrate to PostgreSQL later if needed

**Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` (384 dim, fast, local)

### 1.6 Database Strategy

**Decision:**

- **Client Data:** SQLite (local, one file per client)
- **GST Rules:** PostgreSQL (server, vectorized for LLM search)

**Rationale:**

- Client data must stay local (privacy)
- GST rules need centralized updates (like Cursor's extension system)
- Rules need vector search for LLM semantic queries

### 1.7 LLM Strategy

**Decision:** Hybrid (Claude API + Local Option)
**Rationale:**

- Claude: Better reasoning, understands Indian tax context
- User-provided API keys: True ownership, transparent billing
- Optional local LLM (Ollama): For maximum privacy users

**Privacy Guarantee:** LLM sees only summaries, never raw documents

### 1.8 Rules Engine Architecture

**Decision:** Dual System

1. **Rules Database (PostgreSQL):** Vectorized rules for LLM reference
2. **Rules Engine (Python):** Deterministic logic for calculations

**Rationale:**

- Rules DB: Helps LLM find and explain rules
- Rules Engine: Actually calculates ITC eligibility, amounts
- Separation ensures accuracy (calculations never use LLM)

---

## PART 2: DATABASE SCHEMAS

### 2.1 Client Local Database (SQLite)

```sql
-- Documents table
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    period TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    category TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT UNIQUE,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'indexed',
    metadata JSON
);

-- Document chunks (for vector search)
CREATE TABLE document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB,  -- Vector embedding
    metadata JSON,
    FOREIGN KEY(document_id) REFERENCES documents(id)
);

-- Full-text search index
CREATE VIRTUAL TABLE document_fts USING fts5(
    text,
    metadata UNINDEXED,
    content=document_chunks,
    content_rowid=rowid
);

-- Indexes for performance
CREATE INDEX idx_doc_period ON documents(period, category);
CREATE INDEX idx_chunk_doc_id ON document_chunks(document_id);
```

### 2.2 GST Rules Server Database (PostgreSQL)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Rules table (for LLM reference)
CREATE TABLE gst_rules (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(100) UNIQUE NOT NULL,  -- e.g., "itc_36_4"
    name TEXT NOT NULL,
    rule_text TEXT NOT NULL,
    citation TEXT,
    circular_number TEXT,
    effective_from DATE,
    effective_to DATE,
    category VARCHAR(50),  -- "itc", "blocked_credits", "filing"
    version VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Rule logic (for deterministic calculations)
CREATE TABLE gst_rule_logic (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(100) REFERENCES gst_rules(rule_id),
    condition_type VARCHAR(50) NOT NULL,  -- "vendor_not_in_gstr1", etc.
    condition_logic JSONB NOT NULL,
    action_type VARCHAR(50) NOT NULL,  -- "block_itc", "reverse_itc"
    action_percentage DECIMAL(5,2) DEFAULT 100.0,
    action_amount_formula TEXT,
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector embeddings for semantic search
CREATE TABLE gst_rule_embeddings (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES gst_rules(id),
    embedding vector(384),
    chunk_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector index for fast similarity search
CREATE INDEX ON gst_rule_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Full-text search index
CREATE INDEX ON gst_rules USING GIN (to_tsvector('english', rule_text || ' ' || name));

-- Version tracking
CREATE TABLE gst_rule_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) UNIQUE NOT NULL,
    released_at TIMESTAMP DEFAULT NOW(),
    changelog TEXT,
    rules_count INTEGER
);
```

---

## PART 3: IMPLEMENTATION PLAN

### Phase 1: Foundation (Weeks 1-2)

#### Week 1: Project Setup

- [x] **1.1 Initialize Project Structure**

  - [x] 1.1.1 Create monorepo structure
    - [x] `frontend/` (Tauri + React)
    - [x] `backend/` (Python FastAPI)
    - [x] `server/` (Rules server - PostgreSQL + FastAPI)
    - [x] `shared/` (Type definitions)
  - [x] 1.1.2 Setup version control (Git)
  - [x] 1.1.3 Setup CI/CD basics (GitHub Actions)

- [x] **1.2 Frontend Setup**

  - [x] 1.2.1 Initialize Tauri project
    ```bash
    npm create tauri-app@latest frontend
    ```
  - [x] 1.2.2 Install dependencies
    - [x] React 19, TypeScript 5.5
    - [x] TailwindCSS 4.0
    - [x] shadcn/ui components
    - [x] Zustand (state management)
    - [x] React Query (data fetching)
  - [x] 1.2.3 Setup project structure
    - [x] `src/components/`
    - [x] `src/pages/`
    - [x] `src/hooks/`
    - [x] `src/store/`
    - [x] `src/types/`

- [x] **1.3 Backend Setup**

  - [x] 1.3.1 Initialize Python project
    ```bash
    cd backend
    uv init
    ```
  - [x] 1.3.2 Install core dependencies
    - [x] FastAPI 0.115+
    - [x] Pydantic V2
    - [x] aiosqlite
    - [x] aiofiles
    - [x] httpx (for API calls)
  - [x] 1.3.3 Setup project structure
    - [x] `backend/core/` (firewall, privacy)
    - [x] `backend/services/` (OCR, indexing, etc.)
    - [x] `backend/rules/` (rules engine)
    - [x] `backend/api/` (FastAPI routes)

- [x] **1.4 Rules Server Setup**
  - [x] 1.4.1 Setup PostgreSQL database
    - [x] Install PostgreSQL 16+
    - [x] Install pgvector extension
    - [x] Create database `gst_rules_db`
  - [x] 1.4.2 Initialize FastAPI server
    - [x] Setup project structure
    - [x] Database connection pool
    - [x] Basic API routes

#### Week 2: Core Infrastructure

- [x] **2.1 Workspace Management**

  - [x] 2.1.1 Implement workspace structure
    - [x] Create directory structure on first run
    - [x] Workspace selection UI
    - [x] Workspace validation
  - [x] 2.1.2 Client management
    - [x] Create client workspace
    - [x] Client metadata storage
    - [x] Client list UI

- [x] **2.2 Database Setup**

  - [x] 2.2.1 SQLite initialization
    - [x] Create schema
    - [x] Enable FTS5
    - [x] Setup sqlite-vec extension
    - [x] Performance tuning (WAL mode, cache size)
  - [x] 2.2.2 Database connection management
    - [x] Async connection pool
    - [x] Migration system
    - [x] Backup/restore utilities

- [x] **2.3 Privacy Foundation**
  - [x] 2.3.1 Context Firewall skeleton
    - [x] Tool whitelist registry
    - [x] Parameter validation
    - [x] Result filtering
  - [x] 2.3.2 Audit logging
    - [x] Immutable log structure (JSONL)
    - [x] Log rotation
    - [x] Privacy dashboard data source

### Phase 2: Document Processing (Weeks 3-4)

#### Week 3: OCR & Classification

- [x] **3.1 OCR Engine Integration**

  - [x] 3.1.1 PaddleOCR setup
    - [x] Install PaddleOCR 2.7+
    - [x] Download models
    - [x] Test with sample invoices
  - [x] 3.1.2 Image preprocessing
    - [x] OpenCV integration
    - [x] Deskew algorithm
    - [x] Denoising
    - [x] Contrast enhancement
  - [x] 3.1.3 OCR pipeline
    - [x] PDF to image conversion
    - [x] Multi-page processing
    - [x] Confidence scoring
    - [x] Error handling

- [x] **3.2 Document Classification**

  - [x] 3.2.1 File type detection
    - [x] Magic bytes detection
    - [x] Extension mapping
    - [x] Content sniffing
  - [x] 3.2.2 Document type classifier
    - [x] Invoice detection
    - [x] Statement detection
    - [x] Notice detection
    - [x] Certificate detection
  - [x] 3.2.3 Category classification
    - [x] GST vs IT vs General
    - [x] Sales vs Purchase
    - [x] Period extraction

- [x] **3.3 Document Parser**
  - [x] 3.3.1 Excel parser
    - [x] Multi-sheet support
    - [x] Schema detection
    - [x] GSTR-2B format handling
    - [x] Bank statement parsing
  - [x] 3.3.2 PDF parser
    - [x] Text extraction (non-OCR)
    - [x] Table extraction
    - [x] Form field extraction
  - [x] 3.3.3 Data normalization
    - [x] Standardize column names
    - [x] Data type conversion
    - [x] Validation rules

#### Week 4: Indexing & Storage

- [x] **4.1 Document Indexing**

  - [x] 4.1.1 Embedding generation
    - [x] Sentence-transformers setup
    - [x] Model caching
    - [x] Batch processing
  - [x] 4.1.2 Chunking strategy
    - [x] Smart text splitting
    - [x] Overlap handling
    - [x] Metadata preservation
  - [x] 4.1.3 Vector storage
    - [x] SQLite vector extension
    - [x] Embedding storage (BLOB)
    - [x] Index creation

- [x] **4.2 Search Implementation**

  - [x] 4.2.1 Semantic search
    - [x] Vector similarity query
    - [x] Cosine distance calculation
    - [x] Result ranking
  - [x] 4.2.2 Full-text search
    - [x] FTS5 integration
    - [x] Keyword matching
    - [x] Boolean operators
  - [x] 4.2.3 Hybrid search
    - [x] Combine vector + keyword
    - [x] Result merging
    - [x] Relevance scoring

- [x] **4.3 Async Processing Pipeline**
  - [x] 4.3.1 Queue system
    - [x] Document upload queue
    - [x] Processing status
    - [x] Error handling
  - [x] 4.3.2 Batch processing
    - [x] Concurrent OCR
    - [x] Rate limiting
    - [x] Progress tracking
  - [x] 4.3.3 Caching
    - [x] Embedding cache
    - [x] OCR result cache
    - [x] Search result cache

### Phase 3: Rules Engine (Weeks 5-6)

#### Week 5: Rules Server

- [x] **5.1 Rules Database Setup**

  - [x] 5.1.1 Populate initial rules
    - [x] Rule 36(4) - ITC blocking
    - [x] Rule 42 - ITC reversal
    - [x] Section 17(5) - Blocked credits
    - [x] Basic filing rules
  - [x] 5.1.2 Vectorize rules
    - [x] Generate embeddings
    - [x] Store in PostgreSQL
    - [x] Create vector index
  - [x] 5.1.3 Version management
    - [x] Version tracking
    - [x] Changelog system
    - [x] Rollback capability

- [x] **5.2 Rules API**

  - [x] 5.2.1 Search endpoint
    - [x] Vector similarity search
    - [x] Full-text search fallback
    - [x] Result formatting
  - [x] 5.2.2 Rule retrieval
    - [x] Get by ID
    - [x] Get by category
    - [x] Get latest version
  - [x] 5.2.3 Update system
    - [x] Version check endpoint
    - [x] Bulk download
    - [x] Incremental updates

- [x] **5.3 Client Sync Service**
  - [x] 5.3.1 Rules sync
    - [x] Check for updates
    - [x] Download latest rules
    - [x] Local cache management
  - [x] 5.3.2 Offline fallback
    - [x] Bundled rules (shipped with app)
    - [x] Cache validation
    - [x] Error handling

#### Week 6: Rules Engine Implementation

- [x] **6.1 Rules Engine Core**

  - [x] 6.1.1 Rule logic loader
    - [x] Load from database
    - [x] Parse condition logic
    - [x] Priority sorting
  - [x] 6.1.2 Condition evaluator
    - [x] Vendor in GSTR-2B check
    - [x] Recipient registration check
    - [x] Blocked category check
    - [x] Amount mismatch check
  - [x] 6.1.3 Action executor
    - [x] ITC blocking logic
    - [x] ITC reversal logic
    - [x] Partial ITC logic
    - [x] Amount calculations

- [x] **6.2 ITC Evaluation**

  - [x] 6.2.1 Single invoice evaluation
    - [x] Apply all rules
    - [x] Calculate eligibility
    - [x] Generate explanation
  - [x] 6.2.2 Batch evaluation
    - [x] Process multiple invoices
    - [x] Aggregate results
    - [x] Performance optimization
  - [x] 6.2.3 Working paper generation
    - [x] Summary calculations
    - [x] Detailed breakdown
    - [x] Rule citations
    - [x] Export formats (JSON, Excel)

- [x] **6.3 GSTR-2B Reconciliation**
  - [x] 6.3.1 Invoice matching
    - [x] Match by invoice number
    - [x] Match by amount
    - [x] Fuzzy matching
  - [x] 6.3.2 Difference detection
    - [x] Amount differences
    - [x] Missing invoices
    - [x] Extra invoices
  - [x] 6.3.3 Reconciliation report
    - [x] Matched items
    - [x] Unmatched items
    - [x] Action items

### Phase 4: Context Firewall & Privacy (Weeks 7-8)

#### Week 7: Firewall Implementation

- [x] **7.1 Tool Registry**

  - [x] 7.1.1 Whitelist definition
    - [x] Allowed tools list
    - [x] Access levels (SUMMARY_ONLY, STRUCTURED_DATA)
    - [x] Parameter constraints
  - [x] 7.1.2 Tool implementations
    - [x] `search_documents` tool
    - [x] `get_invoice` tool
    - [x] `get_summary` tool
    - [x] `get_reconciliation` tool
    - [x] `search_gst_rules` tool
    - [x] `explain_rule` tool
  - [x] 7.1.3 Parameter validation
    - [x] Type checking
    - [x] Range validation
    - [x] Path traversal prevention
    - [x] Injection prevention

- [x] **7.2 Result Filtering**

  - [x] 7.2.1 Summary generation
    - [x] Text truncation
    - [x] Field filtering
    - [x] Aggregation only
  - [x] 7.2.2 Structured data extraction
    - [x] Allowed fields only
    - [x] Sensitive data removal
    - [x] Metadata stripping
  - [x] 7.2.3 Preview limits
    - [x] Max preview length
    - [x] Max results count
    - [x] Time-based limits

- [x] **7.3 Audit Logging**
  - [x] 7.3.1 Log structure
    - [x] Timestamp
    - [x] Tool name
    - [x] Parameters (sanitized)
    - [x] Result size
    - [x] User ID
  - [x] 7.3.2 Log storage
    - [x] JSONL format (immutable)
    - [x] Append-only
    - [x] Rotation policy
  - [x] 7.3.3 Log analysis
    - [x] Privacy dashboard data
    - [x] Usage statistics
    - [x] Security monitoring

#### Week 8: Privacy UI & Verification

- [x] **8.1 Privacy Dashboard**

  - [x] 8.1.1 Access summary
    - [x] Total queries
    - [x] Data shared (bytes)
    - [x] Percentage of workspace
  - [x] 8.1.2 Recent interactions
    - [x] Tool calls list
    - [x] Data shared per call
    - [x] Timestamps
  - [x] 8.1.3 Security status
    - [x] Firewall active
    - [x] No file access
    - [x] All interactions logged

- [x] **8.2 Audit Log Viewer**

  - [x] 8.2.1 Log display
    - [x] Filterable list
    - [x] Search functionality
    - [x] Export capability
  - [x] 8.2.2 Detailed view
    - [x] Full log entry
    - [x] Parameter inspection
    - [x] Result preview
  - [x] 8.2.3 Privacy report
    - [x] Generate report
    - [x] PDF export
    - [x] Compliance checklist

- [x] **8.3 Data Management**
  - [x] 8.3.1 Workspace info
    - [x] Location display
    - [x] Size calculation
    - [x] File count
  - [x] 8.3.2 Export functionality
    - [x] Export as ZIP
    - [x] Export processed data
    - [x] Export audit logs
  - [x] 8.3.3 Deletion
    - [x] Delete client data
    - [x] Delete workspace
    - [x] Confirmation dialogs

### Phase 5: LLM Integration (Weeks 9-10)

#### Week 9: LLM Service

- [x] **9.1 Claude API Integration**

  - [x] 9.1.1 API client setup
    - [x] Anthropic SDK
    - [x] API key management
    - [x] Error handling
  - [x] 9.1.2 Tool calling
    - [x] Tool definitions
    - [x] Function calling format
    - [x] Response parsing
  - [x] 9.1.3 Conversation management
    - [x] History tracking
    - [x] Context window management
    - [x] Token counting

- [x] **9.2 System Prompt**

  - [x] 9.2.1 Role definition
    - [x] CA assistant role
    - [x] Constraints and boundaries
    - [x] Indian tax context
  - [x] 9.2.2 Tool documentation
    - [x] Available tools
    - [x] Usage examples
    - [x] Error handling
  - [x] 9.2.3 Prompt engineering
    - [x] Iterative refinement
    - [x] Testing with CAs
    - [x] Performance optimization

- [x] **9.3 Local LLM Option**
  - [x] 9.3.1 Ollama integration
    - [x] Model download
    - [x] API setup
    - [x] Fallback logic
  - [x] 9.3.2 Model selection
    - [x] Recommended models
    - [x] Performance comparison
    - [x] Quality assessment
  - [x] 9.3.3 Settings UI
    - [x] LLM selection
    - [x] API key input
    - [x] Model configuration

#### Week 10: Chat Interface

- [x] **10.1 Chat UI Components**

  - [x] 10.1.1 Message display
    - [x] User messages
    - [x] AI responses
    - [x] Tool call indicators
    - [x] Loading states
  - [x] 10.1.2 Input area
    - [x] Text input
    - [x] Send button
    - [x] File attachments (for context)
    - [x] Keyboard shortcuts
  - [x] 10.1.3 Conversation history
    - [x] Scrollable list
    - [x] Search functionality
    - [x] Export conversation

- [x] **10.2 Response Rendering**

  - [x] 10.2.1 Markdown rendering
    - [x] Text formatting
    - [x] Code blocks
    - [x] Tables
  - [x] 10.2.2 Structured data display
    - [x] Invoice details
    - [x] Summary cards
    - [x] Rule citations
  - [x] 10.2.3 Interactive elements
    - [x] Expandable sections
    - [x] Copy buttons
    - [x] Action buttons

- [x] **10.3 Error Handling**
  - [x] 10.3.1 API errors
    - [x] Network errors
    - [x] Rate limiting
    - [x] Authentication errors
  - [x] 10.3.2 User feedback
    - [x] Error messages
    - [x] Retry mechanisms
    - [x] Help documentation
  - [x] 10.3.3 Fallback behavior
    - [x] Offline mode
    - [x] Cached responses
    - [x] Local LLM fallback

### Phase 6: UI & Polish (Weeks 11-12)

#### Week 11: Main UI

- [x] **11.1 Dashboard**

  - [x] 11.1.1 Client list
    - [x] Grid/list view
    - [x] Search/filter
    - [x] Quick actions
  - [x] 11.1.2 Recent activity
    - [x] Recent documents
    - [x] Recent conversations
    - [x] Pending approvals
  - [x] 11.1.3 Statistics
    - [x] Total clients
    - [x] Documents processed
    - [x] Time saved

- [x] **11.2 Document Management**

  - [x] 11.2.1 Upload interface
    - [x] Drag & drop
    - [x] File picker
    - [x] Batch upload
    - [x] Progress indicators
  - [x] 11.2.2 Document list
    - [x] Filterable table
    - [x] Status indicators
    - [x] Actions menu
  - [x] 11.2.3 Document viewer
    - [x] PDF viewer
    - [x] Image viewer
    - [x] Extracted data display
    - [x] Edit extracted data

- [x] **11.3 GST Filing UI**
  - [x] 11.3.1 Period selection
    - [x] Month/year picker
    - [x] Financial year view
  - [x] 11.3.2 Filing dashboard
    - [x] GSTR-1 status
    - [x] GSTR-3B status
    - [x] ITC summary
    - [x] Reconciliation status
  - [x] 11.3.3 Draft review
    - [x] Draft display
    - [x] Edit capabilities
    - [x] Approval workflow
    - [x] Export options

#### Week 12: Testing & Polish

- [ ] **12.1 Testing**

  - [ ] 12.1.1 Unit tests
    - [ ] Rules engine tests
    - [ ] OCR tests
    - [ ] Firewall tests
  - [ ] 12.1.2 Integration tests
    - [ ] End-to-end workflows
    - [ ] API tests
    - [ ] Database tests
  - [ ] 12.1.3 User testing
    - [ ] Beta CA testing
    - [ ] Feedback collection
    - [ ] Bug fixes

- [ ] **12.2 Performance Optimization**

  - [ ] 12.2.1 Profiling
    - [ ] Identify bottlenecks
    - [ ] Memory leaks
    - [ ] Slow queries
  - [x] 12.2.2 Optimizations
    - [x] Database indexes
    - [x] Caching improvements
    - [x] Async optimizations
  - [ ] 12.2.3 Load testing
    - [ ] Large document sets
    - [ ] Concurrent users
    - [ ] Stress testing

- [x] **12.3 Documentation**
  - [x] 12.3.1 User documentation
    - [x] Getting started guide
    - [x] Feature documentation
    - [ ] FAQ
  - [x] 12.3.2 Developer documentation
    - [x] Architecture overview
    - [x] API documentation
    - [ ] Contribution guide
  - [x] 12.3.3 Deployment guide
    - [x] Build instructions
    - [ ] Distribution setup
    - [ ] Update mechanism

---

## PART 4: KEY IMPLEMENTATION DETAILS

### 4.1 Context Firewall Flow

```
User Query → LLM → Tool Call Request
                    ↓
            Context Firewall
                    ↓
        [Validate Tool] → [Check Whitelist]
                    ↓
        [Execute Tool] → [Get Results]
                    ↓
        [Filter Results] → [Truncate/Summarize]
                    ↓
        [Log to Audit] → [Return to LLM]
                    ↓
        LLM → Response to User
```

### 4.2 Rules Engine Flow

```
Invoice Data → Rules Engine
                    ↓
        [Load Rule Logic from DB]
                    ↓
        [Check Conditions in Priority Order]
                    ↓
        [Apply Matching Rule]
                    ↓
        [Calculate ITC Eligibility]
                    ↓
        [Generate Working Paper]
                    ↓
        [Return Results]
```

### 4.3 Document Processing Flow

```
Upload → Classification → OCR/Parsing
                              ↓
                    Extract Structured Data
                              ↓
                    Generate Embeddings
                              ↓
                    Store in SQLite
                              ↓
                    Index (FTS5 + Vector)
                              ↓
                    Ready for Search
```

---

## PART 5: PERFORMANCE TARGETS

- **Document Processing:** <2s per invoice (async batch)
- **Search:** <100ms for semantic search
- **LLM Response:** <3s (with caching)
- **App Startup:** <2s
- **Memory:** <500MB idle, <2GB processing
- **Database:** <50MB per client (10k documents)

---

## PART 6: SECURITY & PRIVACY CHECKLIST

- [ ] No document uploads to cloud
- [ ] All processing local
- [ ] Context firewall enforced
- [ ] Audit logs immutable
- [ ] User can delete all data
- [ ] Optional encryption at rest
- [ ] API keys stored securely
- [ ] No telemetry/analytics
- [ ] Open source dependencies audited
- [ ] Regular security updates

---

## PART 7: DEPLOYMENT STRATEGY

### 7.1 Build Process

- **Frontend:** Tauri build (native executables)
- **Backend:** PyInstaller or Nuitka (standalone binary)
- **Distribution:** Direct download (no app stores initially)

### 7.2 Update Mechanism

- **Rules:** Auto-sync from server (optional)
- **App:** Manual updates (download new version)
- **Future:** Auto-update system (like Cursor)

### 7.3 Packaging

- **Windows:** `.exe` installer (~200MB)
- **macOS:** `.dmg` package (~200MB)
- **Linux:** `.AppImage` or `.deb` (~200MB)

---

## PART 8: SUCCESS METRICS

### Phase 1 (MVP)

- [ ] 1 CA using daily
- [ ] Can file 1 GST return end-to-end
- [ ] <4 hours per month per client
- [ ] CA approves all filings

### Phase 2 (MVP+)

- [ ] 10 paying beta users
- [ ] > 80% OCR accuracy
- [ ] > 95% user approval rate
- [ ] <$5 cost per filing

### Phase 3 (Launch)

- [ ] 100+ active users
- [ ] > 70% feature adoption
- [ ] NPS > 40
- [ ] Churn < 5%/month

---

## PART 9: RISK MITIGATION

### Risk 1: OCR Accuracy

**Mitigation:**

- Manual review UI for low-confidence extractions
- Start with high-quality vendors
- Continuous improvement from corrections

### Risk 2: Rule Accuracy

**Mitigation:**

- Start with basic rules only
- CA review before filing
- Conservative defaults
- Cite every rule

### Risk 3: Privacy Breach

**Mitigation:**

- Context firewall mandatory
- Audit logs from day 1
- Regular security reviews
- Transparent privacy policy

### Risk 4: Performance

**Mitigation:**

- Async processing
- Caching strategies
- Database optimization
- Profiling and monitoring

---

## PART 10: NEXT STEPS

1. **This Week:**

   - Review and approve this TDR
   - Setup development environment
   - Initialize project structure

2. **Week 1-2:**

   - Begin Phase 1 implementation
   - Setup all infrastructure
   - Create initial UI mockups

3. **Ongoing:**
   - Weekly progress reviews
   - Continuous testing
   - Early CA feedback

---

## APPENDIX: TECHNOLOGY VERSIONS

- **Tauri:** 2.0+
- **React:** 19.0+
- **TypeScript:** 5.5+
- **Python:** 3.12+
- **FastAPI:** 0.115+
- **PostgreSQL:** 16+
- **pgvector:** 0.5+
- **PaddleOCR:** 2.7+
- **sentence-transformers:** 2.7+
- **SQLite:** 3.46+

---

**Document Status:** Finalized  
**Last Updated:** 2024-12-15  
**Next Review:** After Phase 1 completion

This TDR includes:

- Finalized technical decisions with rationale
- Database schemas for client and rules
- 12-week implementation plan with nested steps
- Performance targets and success metrics
- Risk mitigation strategies
- Security and privacy checklist

Use this as the implementation guide. Each phase builds on the previous one, with clear deliverables and checkpoints.

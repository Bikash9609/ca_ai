Creating ENGINEER_TDR.md with finalized decisions and a step-by-step implementation plan.


[1 tool called]


Creating ENGINEER_TDR.md with finalized decisions and a step-by-step implementation plan:

```markdown:ENGINEER_TDR.md
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
- [ ] **1.1 Initialize Project Structure**
  - [ ] 1.1.1 Create monorepo structure
    - [ ] `frontend/` (Tauri + React)
    - [ ] `backend/` (Python FastAPI)
    - [ ] `server/` (Rules server - PostgreSQL + FastAPI)
    - [ ] `shared/` (Type definitions)
  - [ ] 1.1.2 Setup version control (Git)
  - [ ] 1.1.3 Setup CI/CD basics (GitHub Actions)

- [ ] **1.2 Frontend Setup**
  - [ ] 1.2.1 Initialize Tauri project
    ```bash
    npm create tauri-app@latest frontend
    ```
  - [ ] 1.2.2 Install dependencies
    - [ ] React 19, TypeScript 5.5
    - [ ] TailwindCSS 4.0
    - [ ] shadcn/ui components
    - [ ] Zustand (state management)
    - [ ] React Query (data fetching)
  - [ ] 1.2.3 Setup project structure
    - [ ] `src/components/`
    - [ ] `src/pages/`
    - [ ] `src/hooks/`
    - [ ] `src/store/`
    - [ ] `src/types/`

- [ ] **1.3 Backend Setup**
  - [ ] 1.3.1 Initialize Python project
    ```bash
    cd backend
    uv init
    ```
  - [ ] 1.3.2 Install core dependencies
    - [ ] FastAPI 0.115+
    - [ ] Pydantic V2
    - [ ] aiosqlite
    - [ ] aiofiles
    - [ ] httpx (for API calls)
  - [ ] 1.3.3 Setup project structure
    - [ ] `backend/core/` (firewall, privacy)
    - [ ] `backend/services/` (OCR, indexing, etc.)
    - [ ] `backend/rules/` (rules engine)
    - [ ] `backend/api/` (FastAPI routes)

- [ ] **1.4 Rules Server Setup**
  - [ ] 1.4.1 Setup PostgreSQL database
    - [ ] Install PostgreSQL 16+
    - [ ] Install pgvector extension
    - [ ] Create database `gst_rules_db`
  - [ ] 1.4.2 Initialize FastAPI server
    - [ ] Setup project structure
    - [ ] Database connection pool
    - [ ] Basic API routes

#### Week 2: Core Infrastructure
- [ ] **2.1 Workspace Management**
  - [ ] 2.1.1 Implement workspace structure
    - [ ] Create directory structure on first run
    - [ ] Workspace selection UI
    - [ ] Workspace validation
  - [ ] 2.1.2 Client management
    - [ ] Create client workspace
    - [ ] Client metadata storage
    - [ ] Client list UI

- [ ] **2.2 Database Setup**
  - [ ] 2.2.1 SQLite initialization
    - [ ] Create schema
    - [ ] Enable FTS5
    - [ ] Setup sqlite-vec extension
    - [ ] Performance tuning (WAL mode, cache size)
  - [ ] 2.2.2 Database connection management
    - [ ] Async connection pool
    - [ ] Migration system
    - [ ] Backup/restore utilities

- [ ] **2.3 Privacy Foundation**
  - [ ] 2.3.1 Context Firewall skeleton
    - [ ] Tool whitelist registry
    - [ ] Parameter validation
    - [ ] Result filtering
  - [ ] 2.3.2 Audit logging
    - [ ] Immutable log structure (JSONL)
    - [ ] Log rotation
    - [ ] Privacy dashboard data source

### Phase 2: Document Processing (Weeks 3-4)

#### Week 3: OCR & Classification
- [ ] **3.1 OCR Engine Integration**
  - [ ] 3.1.1 PaddleOCR setup
    - [ ] Install PaddleOCR 2.7+
    - [ ] Download models
    - [ ] Test with sample invoices
  - [ ] 3.1.2 Image preprocessing
    - [ ] OpenCV integration
    - [ ] Deskew algorithm
    - [ ] Denoising
    - [ ] Contrast enhancement
  - [ ] 3.1.3 OCR pipeline
    - [ ] PDF to image conversion
    - [ ] Multi-page processing
    - [ ] Confidence scoring
    - [ ] Error handling

- [ ] **3.2 Document Classification**
  - [ ] 3.2.1 File type detection
    - [ ] Magic bytes detection
    - [ ] Extension mapping
    - [ ] Content sniffing
  - [ ] 3.2.2 Document type classifier
    - [ ] Invoice detection
    - [ ] Statement detection
    - [ ] Notice detection
    - [ ] Certificate detection
  - [ ] 3.2.3 Category classification
    - [ ] GST vs IT vs General
    - [ ] Sales vs Purchase
    - [ ] Period extraction

- [ ] **3.3 Document Parser**
  - [ ] 3.3.1 Excel parser
    - [ ] Multi-sheet support
    - [ ] Schema detection
    - [ ] GSTR-2B format handling
    - [ ] Bank statement parsing
  - [ ] 3.3.2 PDF parser
    - [ ] Text extraction (non-OCR)
    - [ ] Table extraction
    - [ ] Form field extraction
  - [ ] 3.3.3 Data normalization
    - [ ] Standardize column names
    - [ ] Data type conversion
    - [ ] Validation rules

#### Week 4: Indexing & Storage
- [ ] **4.1 Document Indexing**
  - [ ] 4.1.1 Embedding generation
    - [ ] Sentence-transformers setup
    - [ ] Model caching
    - [ ] Batch processing
  - [ ] 4.1.2 Chunking strategy
    - [ ] Smart text splitting
    - [ ] Overlap handling
    - [ ] Metadata preservation
  - [ ] 4.1.3 Vector storage
    - [ ] SQLite vector extension
    - [ ] Embedding storage (BLOB)
    - [ ] Index creation

- [ ] **4.2 Search Implementation**
  - [ ] 4.2.1 Semantic search
    - [ ] Vector similarity query
    - [ ] Cosine distance calculation
    - [ ] Result ranking
  - [ ] 4.2.2 Full-text search
    - [ ] FTS5 integration
    - [ ] Keyword matching
    - [ ] Boolean operators
  - [ ] 4.2.3 Hybrid search
    - [ ] Combine vector + keyword
    - [ ] Result merging
    - [ ] Relevance scoring

- [ ] **4.3 Async Processing Pipeline**
  - [ ] 4.3.1 Queue system
    - [ ] Document upload queue
    - [ ] Processing status
    - [ ] Error handling
  - [ ] 4.3.2 Batch processing
    - [ ] Concurrent OCR
    - [ ] Rate limiting
    - [ ] Progress tracking
  - [ ] 4.3.3 Caching
    - [ ] Embedding cache
    - [ ] OCR result cache
    - [ ] Search result cache

### Phase 3: Rules Engine (Weeks 5-6)

#### Week 5: Rules Server
- [ ] **5.1 Rules Database Setup**
  - [ ] 5.1.1 Populate initial rules
    - [ ] Rule 36(4) - ITC blocking
    - [ ] Rule 42 - ITC reversal
    - [ ] Section 17(5) - Blocked credits
    - [ ] Basic filing rules
  - [ ] 5.1.2 Vectorize rules
    - [ ] Generate embeddings
    - [ ] Store in PostgreSQL
    - [ ] Create vector index
  - [ ] 5.1.3 Version management
    - [ ] Version tracking
    - [ ] Changelog system
    - [ ] Rollback capability

- [ ] **5.2 Rules API**
  - [ ] 5.2.1 Search endpoint
    - [ ] Vector similarity search
    - [ ] Full-text search fallback
    - [ ] Result formatting
  - [ ] 5.2.2 Rule retrieval
    - [ ] Get by ID
    - [ ] Get by category
    - [ ] Get latest version
  - [ ] 5.2.3 Update system
    - [ ] Version check endpoint
    - [ ] Bulk download
    - [ ] Incremental updates

- [ ] **5.3 Client Sync Service**
  - [ ] 5.3.1 Rules sync
    - [ ] Check for updates
    - [ ] Download latest rules
    - [ ] Local cache management
  - [ ] 5.3.2 Offline fallback
    - [ ] Bundled rules (shipped with app)
    - [ ] Cache validation
    - [ ] Error handling

#### Week 6: Rules Engine Implementation
- [ ] **6.1 Rules Engine Core**
  - [ ] 6.1.1 Rule logic loader
    - [ ] Load from database
    - [ ] Parse condition logic
    - [ ] Priority sorting
  - [ ] 6.1.2 Condition evaluator
    - [ ] Vendor in GSTR-2B check
    - [ ] Recipient registration check
    - [ ] Blocked category check
    - [ ] Amount mismatch check
  - [ ] 6.1.3 Action executor
    - [ ] ITC blocking logic
    - [ ] ITC reversal logic
    - [ ] Partial ITC logic
    - [ ] Amount calculations

- [ ] **6.2 ITC Evaluation**
  - [ ] 6.2.1 Single invoice evaluation
    - [ ] Apply all rules
    - [ ] Calculate eligibility
    - [ ] Generate explanation
  - [ ] 6.2.2 Batch evaluation
    - [ ] Process multiple invoices
    - [ ] Aggregate results
    - [ ] Performance optimization
  - [ ] 6.2.3 Working paper generation
    - [ ] Summary calculations
    - [ ] Detailed breakdown
    - [ ] Rule citations
    - [ ] Export formats (JSON, Excel)

- [ ] **6.3 GSTR-2B Reconciliation**
  - [ ] 6.3.1 Invoice matching
    - [ ] Match by invoice number
    - [ ] Match by amount
    - [ ] Fuzzy matching
  - [ ] 6.3.2 Difference detection
    - [ ] Amount differences
    - [ ] Missing invoices
    - [ ] Extra invoices
  - [ ] 6.3.3 Reconciliation report
    - [ ] Matched items
    - [ ] Unmatched items
    - [ ] Action items

### Phase 4: Context Firewall & Privacy (Weeks 7-8)

#### Week 7: Firewall Implementation
- [ ] **7.1 Tool Registry**
  - [ ] 7.1.1 Whitelist definition
    - [ ] Allowed tools list
    - [ ] Access levels (SUMMARY_ONLY, STRUCTURED_DATA)
    - [ ] Parameter constraints
  - [ ] 7.1.2 Tool implementations
    - [ ] `search_documents` tool
    - [ ] `get_invoice` tool
    - [ ] `get_summary` tool
    - [ ] `get_reconciliation` tool
    - [ ] `search_gst_rules` tool
    - [ ] `explain_rule` tool
  - [ ] 7.1.3 Parameter validation
    - [ ] Type checking
    - [ ] Range validation
    - [ ] Path traversal prevention
    - [ ] Injection prevention

- [ ] **7.2 Result Filtering**
  - [ ] 7.2.1 Summary generation
    - [ ] Text truncation
    - [ ] Field filtering
    - [ ] Aggregation only
  - [ ] 7.2.2 Structured data extraction
    - [ ] Allowed fields only
    - [ ] Sensitive data removal
    - [ ] Metadata stripping
  - [ ] 7.2.3 Preview limits
    - [ ] Max preview length
    - [ ] Max results count
    - [ ] Time-based limits

- [ ] **7.3 Audit Logging**
  - [ ] 7.3.1 Log structure
    - [ ] Timestamp
    - [ ] Tool name
    - [ ] Parameters (sanitized)
    - [ ] Result size
    - [ ] User ID
  - [ ] 7.3.2 Log storage
    - [ ] JSONL format (immutable)
    - [ ] Append-only
    - [ ] Rotation policy
  - [ ] 7.3.3 Log analysis
    - [ ] Privacy dashboard data
    - [ ] Usage statistics
    - [ ] Security monitoring

#### Week 8: Privacy UI & Verification
- [ ] **8.1 Privacy Dashboard**
  - [ ] 8.1.1 Access summary
    - [ ] Total queries
    - [ ] Data shared (bytes)
    - [ ] Percentage of workspace
  - [ ] 8.1.2 Recent interactions
    - [ ] Tool calls list
    - [ ] Data shared per call
    - [ ] Timestamps
  - [ ] 8.1.3 Security status
    - [ ] Firewall active
    - [ ] No file access
    - [ ] All interactions logged

- [ ] **8.2 Audit Log Viewer**
  - [ ] 8.2.1 Log display
    - [ ] Filterable list
    - [ ] Search functionality
    - [ ] Export capability
  - [ ] 8.2.2 Detailed view
    - [ ] Full log entry
    - [ ] Parameter inspection
    - [ ] Result preview
  - [ ] 8.2.3 Privacy report
    - [ ] Generate report
    - [ ] PDF export
    - [ ] Compliance checklist

- [ ] **8.3 Data Management**
  - [ ] 8.3.1 Workspace info
    - [ ] Location display
    - [ ] Size calculation
    - [ ] File count
  - [ ] 8.3.2 Export functionality
    - [ ] Export as ZIP
    - [ ] Export processed data
    - [ ] Export audit logs
  - [ ] 8.3.3 Deletion
    - [ ] Delete client data
    - [ ] Delete workspace
    - [ ] Confirmation dialogs

### Phase 5: LLM Integration (Weeks 9-10)

#### Week 9: LLM Service
- [ ] **9.1 Claude API Integration**
  - [ ] 9.1.1 API client setup
    - [ ] Anthropic SDK
    - [ ] API key management
    - [ ] Error handling
  - [ ] 9.1.2 Tool calling
    - [ ] Tool definitions
    - [ ] Function calling format
    - [ ] Response parsing
  - [ ] 9.1.3 Conversation management
    - [ ] History tracking
    - [ ] Context window management
    - [ ] Token counting

- [ ] **9.2 System Prompt**
  - [ ] 9.2.1 Role definition
    - [ ] CA assistant role
    - [ ] Constraints and boundaries
    - [ ] Indian tax context
  - [ ] 9.2.2 Tool documentation
    - [ ] Available tools
    - [ ] Usage examples
    - [ ] Error handling
  - [ ] 9.2.3 Prompt engineering
    - [ ] Iterative refinement
    - [ ] Testing with CAs
    - [ ] Performance optimization

- [ ] **9.3 Local LLM Option**
  - [ ] 9.3.1 Ollama integration
    - [ ] Model download
    - [ ] API setup
    - [ ] Fallback logic
  - [ ] 9.3.2 Model selection
    - [ ] Recommended models
    - [ ] Performance comparison
    - [ ] Quality assessment
  - [ ] 9.3.3 Settings UI
    - [ ] LLM selection
    - [ ] API key input
    - [ ] Model configuration

#### Week 10: Chat Interface
- [ ] **10.1 Chat UI Components**
  - [ ] 10.1.1 Message display
    - [ ] User messages
    - [ ] AI responses
    - [ ] Tool call indicators
    - [ ] Loading states
  - [ ] 10.1.2 Input area
    - [ ] Text input
    - [ ] Send button
    - [ ] File attachments (for context)
    - [ ] Keyboard shortcuts
  - [ ] 10.1.3 Conversation history
    - [ ] Scrollable list
    - [ ] Search functionality
    - [ ] Export conversation

- [ ] **10.2 Response Rendering**
  - [ ] 10.2.1 Markdown rendering
    - [ ] Text formatting
    - [ ] Code blocks
    - [ ] Tables
  - [ ] 10.2.2 Structured data display
    - [ ] Invoice details
    - [ ] Summary cards
    - [ ] Rule citations
  - [ ] 10.2.3 Interactive elements
    - [ ] Expandable sections
    - [ ] Copy buttons
    - [ ] Action buttons

- [ ] **10.3 Error Handling**
  - [ ] 10.3.1 API errors
    - [ ] Network errors
    - [ ] Rate limiting
    - [ ] Authentication errors
  - [ ] 10.3.2 User feedback
    - [ ] Error messages
    - [ ] Retry mechanisms
    - [ ] Help documentation
  - [ ] 10.3.3 Fallback behavior
    - [ ] Offline mode
    - [ ] Cached responses
    - [ ] Local LLM fallback

### Phase 6: UI & Polish (Weeks 11-12)

#### Week 11: Main UI
- [ ] **11.1 Dashboard**
  - [ ] 11.1.1 Client list
    - [ ] Grid/list view
    - [ ] Search/filter
    - [ ] Quick actions
  - [ ] 11.1.2 Recent activity
    - [ ] Recent documents
    - [ ] Recent conversations
    - [ ] Pending approvals
  - [ ] 11.1.3 Statistics
    - [ ] Total clients
    - [ ] Documents processed
    - [ ] Time saved

- [ ] **11.2 Document Management**
  - [ ] 11.2.1 Upload interface
    - [ ] Drag & drop
    - [ ] File picker
    - [ ] Batch upload
    - [ ] Progress indicators
  - [ ] 11.2.2 Document list
    - [ ] Filterable table
    - [ ] Status indicators
    - [ ] Actions menu
  - [ ] 11.2.3 Document viewer
    - [ ] PDF viewer
    - [ ] Image viewer
    - [ ] Extracted data display
    - [ ] Edit extracted data

- [ ] **11.3 GST Filing UI**
  - [ ] 11.3.1 Period selection
    - [ ] Month/year picker
    - [ ] Financial year view
  - [ ] 11.3.2 Filing dashboard
    - [ ] GSTR-1 status
    - [ ] GSTR-3B status
    - [ ] ITC summary
    - [ ] Reconciliation status
  - [ ] 11.3.3 Draft review
    - [ ] Draft display
    - [ ] Edit capabilities
    - [ ] Approval workflow
    - [ ] Export options

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
  - [ ] 12.2.2 Optimizations
    - [ ] Database indexes
    - [ ] Caching improvements
    - [ ] Async optimizations
  - [ ] 12.2.3 Load testing
    - [ ] Large document sets
    - [ ] Concurrent users
    - [ ] Stress testing

- [ ] **12.3 Documentation**
  - [ ] 12.3.1 User documentation
    - [ ] Getting started guide
    - [ ] Feature documentation
    - [ ] FAQ
  - [ ] 12.3.2 Developer documentation
    - [ ] Architecture overview
    - [ ] API documentation
    - [ ] Contribution guide
  - [ ] 12.3.3 Deployment guide
    - [ ] Build instructions
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
- [ ] >80% OCR accuracy
- [ ] >95% user approval rate
- [ ] <$5 cost per filing

### Phase 3 (Launch)
- [ ] 100+ active users
- [ ] >70% feature adoption
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
```

This TDR includes:
- Finalized technical decisions with rationale
- Database schemas for client and rules
- 12-week implementation plan with nested steps
- Performance targets and success metrics
- Risk mitigation strategies
- Security and privacy checklist

Use this as the implementation guide. Each phase builds on the previous one, with clear deliverables and checkpoints.
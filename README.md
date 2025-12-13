# CA AI MVP

A local-first, privacy-preserving application for Chartered Accountants to manage GST compliance with AI assistance.

## Architecture

This is a monorepo containing:

- **frontend/**: Tauri 2.0 + React 19 + TypeScript 5.5 desktop application
- **backend/**: Python 3.12+ + FastAPI 0.115+ local processing engine
- **server/**: Rules server (PostgreSQL + FastAPI) for GST rules management
- **shared/**: Shared TypeScript type definitions

## Core Principle

**Documents never leave user's machine. LLM sees only summaries (Cursor-style architecture).**

## Getting Started

### Prerequisites

- Node.js 20+ and Yarn
- Python 3.12+
- PostgreSQL 16+ (for rules server)
- Rust (for Tauri)

### Setup

1. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Frontend Setup**
   ```bash
   cd frontend
   yarn install
   ```

3. **Rules Server Setup**
   ```bash
   cd server
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Shared Types**
   ```bash
   cd shared
   yarn install
   ```

## Development

See `ENGINEER_TDR.md` for detailed architecture and implementation plan.

## License

[To be determined]


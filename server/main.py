"""
CA AI MVP Rules Server - Main Application Entry Point
PostgreSQL-based rules server for GST rules management
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from server.database.connection import DatabasePool
from server.database.init import initialize_database, check_database_connection, check_pgvector_extension
from server.api.rules import router as rules_router
from server.api.versions import router as versions_router

# Global database pool
db_pool: DatabasePool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global db_pool
    
    # Startup
    db_pool = DatabasePool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "gst_rules_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
    )
    
    await db_pool.create_pool()
    
    # Check connection
    if not await check_database_connection(db_pool):
        raise RuntimeError("Failed to connect to database")
    
    # Check pgvector extension
    if not await check_pgvector_extension(db_pool):
        print("Warning: pgvector extension not found. Vector search will not work.")
    
    # Initialize schema if needed
    schema_file = Path(__file__).parent / "database" / "schema.sql"
    if schema_file.exists():
        try:
            await initialize_database(db_pool, schema_file)
        except Exception as e:
            print(f"Warning: Schema initialization failed: {e}")
    
    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close_pool()


app = FastAPI(
    title="CA AI Rules Server",
    description="GST Rules Server for CA AI MVP",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Rules server can be accessed from anywhere
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




# Include API routes
app.include_router(rules_router, prefix="/api/v1", tags=["rules"])
app.include_router(versions_router, prefix="/api/v1", tags=["versions"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "CA AI Rules Server"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


"""
CA AI MVP Backend - Main Application Entry Point
Local processing engine for document processing and AI assistance
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="CA AI Backend",
    description="Local processing engine for CA AI MVP",
    version="0.1.0",
)

# CORS middleware for Tauri frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "CA AI Backend"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


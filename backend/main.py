"""
CA AI MVP Backend - Main Application Entry Point
Local processing engine for document processing and AI assistance
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import traceback
import asyncio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from api.routes import router
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CA AI Backend",
    description="Local processing engine for CA AI MVP",
    version="0.1.0",
)

# CORS middleware for Tauri frontend and browser dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "tauri://localhost",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware to log all requests and errors
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests and responses"""
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            logger.error(
                f"{request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Client: {request.client.host if request.client else 'unknown'}"
            )
        return response
    except Exception as e:
        logger.error(
            f"Unhandled exception in middleware: {e}\n"
            f"Request: {request.method} {request.url.path}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        raise


# Global exception handler for all unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and log them"""
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}\n"
        f"Request: {request.method} {request.url.path}\n"
        f"Traceback: {traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}"}
    )


# Handler for HTTP exceptions
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Log HTTP exceptions"""
    logger.error(
        f"HTTP {exc.status_code}: {exc.detail}\n"
        f"Request: {request.method} {request.url.path}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


# Handler for validation errors (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors"""
    logger.error(
        f"Validation error (422): {exc.errors()}\n"
        f"Request: {request.method} {request.url.path}\n"
        f"Query params: {dict(request.query_params)}"
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": "Validation failed"}
    )


# Include API routes
app.include_router(router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Startup event - initialize services"""
    logger.info("CA AI Backend starting up...")
    
    # Process pending documents in background (non-blocking)
    from api.documents import process_pending_documents_batch
    asyncio.create_task(process_pending_documents_batch())
    logger.info("Started processing pending documents in background")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event - cleanup"""
    from api.documents import _processing_queues
    logger.info("Shutting down processing queues...")
    for queue in _processing_queues.values():
        if queue.is_running:
            await queue.stop()
    logger.info("Shutdown complete")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "CA AI Backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


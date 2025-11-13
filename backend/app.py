"""FastAPI application entry point."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, RedirectResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.routes import router
from backend.database import init_db
from backend.config import settings
from backend.cleanup import cleanup_expired_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests for debugging."""
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        # Log request details
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"Response: {request.method} {request.url.path} "
                f"status={response.status_code} time={process_time:.3f}s"
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Error: {request.method} {request.url.path} "
                f"error={str(e)} time={process_time:.3f}s"
            )
            raise


class NullOriginCORSMiddleware(BaseHTTPMiddleware):
    """Middleware to handle null origin for mobile browsers before CORS middleware."""
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        # Check if this is a null origin request (mobile browsers)
        is_null_origin = origin == "null" or (origin is None and "access-control-request-method" in request.headers)
        
        # Handle OPTIONS preflight requests with null origin
        if request.method == "OPTIONS" and is_null_origin:
            # Allow null origin for preflight
            # Use "*" for Access-Control-Allow-Origin with null origin
            # (browsers accept "*" for null origin when credentials aren't used)
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, DELETE, PUT, PATCH, HEAD"
            requested_headers = request.headers.get("access-control-request-headers", "content-type")
            response.headers["Access-Control-Allow-Headers"] = requested_headers
            response.headers["Access-Control-Max-Age"] = "600"
            return response
        
        # Process the request
        response = await call_next(request)
        
        # For actual requests with null origin, ensure CORS headers are set correctly
        if is_null_origin and request.method != "OPTIONS":
            # Override CORS headers for null origin
            # Use "*" for null origin (browsers accept this when no credentials)
            response.headers["Access-Control-Allow-Origin"] = "*"
            # Remove credentials header if present (browsers reject null origin with credentials)
            if "access-control-allow-credentials" in response.headers:
                del response.headers["access-control-allow-credentials"]
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    init_db()
    
    # Start background cleanup task
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(3600)  # Run every hour
            try:
                cleanup_expired_data()
            except Exception as e:
                print(f"Periodic cleanup error: {e}")
    
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    yield
    
    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# Initialize FastAPI app
app = FastAPI(
    title="WhatsApp Recommendations Extractor API",
    description="API for extracting and processing WhatsApp chat recommendations",
    version="1.0.0",
    lifespan=lifespan
)

# Add request logging middleware (before CORS to catch all requests)
app.add_middleware(RequestLoggingMiddleware)

# Configure CORS with support for null origin (mobile browsers)
# Build allowed origins list including null for mobile browser compatibility
cors_origins = settings.cors_origins_list.copy()
# Add "null" as a string to allow mobile browsers that send Origin: null
if "null" not in cors_origins:
    cors_origins.append("null")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add null origin CORS handler AFTER CORS middleware so it runs FIRST
# This handles mobile browsers that send Origin: null
# (In Starlette, last middleware added runs first, so this intercepts before CORSMiddleware)
app.add_middleware(NullOriginCORSMiddleware)

# Include routers
app.include_router(router)


@app.get("/")
@app.head("/")
async def root():
    """Root endpoint."""
    return {
        "message": "WhatsApp Recommendations Extractor API",
        "docs": "/docs",
        "health": "/api/health"
    }


@app.get("/favicon.ico")
async def favicon():
    """Serve the favicon PNG file."""
    favicon_path = Path(__file__).parent / "static" / "favicon.png"
    if favicon_path.exists():
        return FileResponse(
            favicon_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=31536000"}  # Cache for 1 year
        )
    return Response(status_code=204)  # No content if file doesn't exist


@app.get("/api/")
async def api_root():
    return RedirectResponse(url="/docs")


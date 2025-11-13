"""FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, RedirectResponse, FileResponse

from backend.routes import router
from backend.database import init_db
from backend.config import settings
from backend.cleanup import cleanup_expired_data


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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


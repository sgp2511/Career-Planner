"""
FastAPI application entry point.

Configures the app, middleware, and includes all routers.
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import engine, Base
from app.data_loader import get_available_combinations

# Import all models so Base.metadata.create_all() discovers every table
from app.models import User, Plan  # noqa: F401
from app.routers import auth as auth_router
from app.routers import plans as plans_router

settings = get_settings()

# ---------------------------------------------------------------------------
# Create all database tables on startup (no Alembic for assessment scope)
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# FastAPI app instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "A personalised career relocation planner API. "
        "Takes a user's career profile, target role, destination country, "
        "salary expectation, timeline, and work authorisation constraints, "
        "and returns a ranked action plan with feasibility assessment."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler to prevent 500 errors from leaking internal details."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# ---------------------------------------------------------------------------
# Health & info endpoints (public — no auth required)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for monitoring and container orchestration."""
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/api/v1/info", tags=["System"])
async def app_info():
    """
    Returns application metadata and available destination–role combinations.
    Useful for clients to discover what data the system supports.
    """
    available = get_available_combinations()
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "available_destinations": available,
    }


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(plans_router.router)

# ---------------------------------------------------------------------------
# Serve static UI
# ---------------------------------------------------------------------------
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serve the single-page UI at the root URL."""
    return FileResponse(os.path.join(static_dir, "index.html"))

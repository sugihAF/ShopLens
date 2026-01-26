"""Health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import get_db
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.
    Returns system status and version information.
    """
    # Check database connectivity
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": settings.VERSION,
        "service": settings.PROJECT_NAME,
        "database": db_status,
    }


@router.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "message": "ShopLens API - AI-powered product review intelligence",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
    }

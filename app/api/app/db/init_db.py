"""Database initialization utilities."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import engine
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_tables() -> None:
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def drop_tables() -> None:
    """Drop all database tables (use with caution!)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("Database tables dropped")


async def init_db(db: AsyncSession) -> None:
    """Initialize database with seed data if needed."""
    # Import models to ensure they're registered
    from app.models import product, reviewer, review, opinion, consensus, user, conversation

    logger.info("Database initialization complete")

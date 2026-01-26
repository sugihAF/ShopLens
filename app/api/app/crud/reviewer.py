"""CRUD operations for Reviewer model."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.reviewer import Reviewer, Platform
from app.schemas.common import Message


class ReviewerCreate(Message):
    """Schema for creating a reviewer (simplified)."""
    pass


class ReviewerUpdate(Message):
    """Schema for updating a reviewer (simplified)."""
    pass


class CRUDReviewer(CRUDBase[Reviewer, ReviewerCreate, ReviewerUpdate]):
    """CRUD operations for Reviewer model."""

    async def get_by_platform_id(
        self,
        db: AsyncSession,
        platform_id: str
    ) -> Optional[Reviewer]:
        """Get reviewer by platform-specific ID."""
        result = await db.execute(
            select(Reviewer).where(Reviewer.platform_id == platform_id)
        )
        return result.scalar_one_or_none()

    async def get_by_platform(
        self,
        db: AsyncSession,
        *,
        platform: Platform,
        skip: int = 0,
        limit: int = 50
    ) -> List[Reviewer]:
        """Get reviewers by platform."""
        result = await db.execute(
            select(Reviewer)
            .where(Reviewer.platform == platform)
            .where(Reviewer.is_active == True)
            .order_by(Reviewer.credibility_score.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_reviewers(
        self,
        db: AsyncSession,
        limit: int = 100
    ) -> List[Reviewer]:
        """Get all active reviewers ordered by credibility."""
        result = await db.execute(
            select(Reviewer)
            .where(Reviewer.is_active == True)
            .order_by(Reviewer.credibility_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search(
        self,
        db: AsyncSession,
        *,
        query: str,
        limit: int = 20
    ) -> List[Reviewer]:
        """Search reviewers by name."""
        search_term = f"%{query}%"
        result = await db.execute(
            select(Reviewer)
            .where(Reviewer.name.ilike(search_term))
            .where(Reviewer.is_active == True)
            .order_by(Reviewer.credibility_score.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


reviewer_crud = CRUDReviewer(Reviewer)

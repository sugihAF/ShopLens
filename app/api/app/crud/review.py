"""CRUD operations for Review model."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.review import Review, ProcessingStatus
from app.schemas.common import Message


class ReviewCreate(Message):
    """Schema for creating a review (simplified)."""
    pass


class ReviewUpdate(Message):
    """Schema for updating a review (simplified)."""
    pass


class CRUDReview(CRUDBase[Review, ReviewCreate, ReviewUpdate]):
    """CRUD operations for Review model."""

    async def get_with_relations(
        self,
        db: AsyncSession,
        id: int
    ) -> Optional[Review]:
        """Get review with reviewer and opinions loaded."""
        result = await db.execute(
            select(Review)
            .options(
                selectinload(Review.reviewer),
                selectinload(Review.opinions)
            )
            .where(Review.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_product(
        self,
        db: AsyncSession,
        *,
        product_id: int,
        limit: int = 10
    ) -> List[Review]:
        """Get reviews for a product with reviewer info."""
        result = await db.execute(
            select(Review)
            .options(selectinload(Review.reviewer))
            .where(Review.product_id == product_id)
            .order_by(Review.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_reviewer(
        self,
        db: AsyncSession,
        *,
        reviewer_id: int,
        skip: int = 0,
        limit: int = 20
    ) -> List[Review]:
        """Get reviews by a specific reviewer."""
        result = await db.execute(
            select(Review)
            .options(selectinload(Review.product))
            .where(Review.reviewer_id == reviewer_id)
            .order_by(Review.published_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_reviews(
        self,
        db: AsyncSession,
        limit: int = 50
    ) -> List[Review]:
        """Get reviews pending processing."""
        result = await db.execute(
            select(Review)
            .where(Review.processing_status == ProcessingStatus.PENDING)
            .order_by(Review.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_platform_url(
        self,
        db: AsyncSession,
        platform_url: str
    ) -> Optional[Review]:
        """Get review by platform URL (to check for duplicates)."""
        result = await db.execute(
            select(Review).where(Review.platform_url == platform_url)
        )
        return result.scalar_one_or_none()

    async def update_processing_status(
        self,
        db: AsyncSession,
        review_id: int,
        status: ProcessingStatus
    ) -> Optional[Review]:
        """Update the processing status of a review."""
        review = await self.get(db, id=review_id)
        if review:
            review.processing_status = status
            if status == ProcessingStatus.COMPLETED:
                review.is_processed = True
            db.add(review)
            await db.flush()
            await db.refresh(review)
        return review


review_crud = CRUDReview(Review)

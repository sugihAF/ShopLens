"""CRUD operations for Opinion model."""

from typing import List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.crud.base import CRUDBase
from app.models.opinion import Opinion


class OpinionCreate(BaseModel):
    """Schema for creating an opinion."""
    review_id: int
    aspect: str
    sentiment: float
    confidence: float
    quote: str | None = None
    summary: str | None = None


class OpinionUpdate(BaseModel):
    """Schema for updating an opinion."""
    sentiment: float | None = None
    confidence: float | None = None
    quote: str | None = None
    summary: str | None = None


class CRUDOpinion(CRUDBase[Opinion, OpinionCreate, OpinionUpdate]):
    """CRUD operations for Opinion model."""

    async def bulk_create(
        self,
        db: AsyncSession,
        opinions: list[dict],
    ) -> List[Opinion]:
        """Bulk insert opinions."""
        objs = []
        for data in opinions:
            obj = Opinion(
                review_id=data["review_id"],
                aspect=data["aspect"],
                sentiment=data["sentiment"],
                confidence=data["confidence"],
                quote=data.get("quote"),
                summary=data.get("summary"),
            )
            db.add(obj)
            objs.append(obj)
        await db.flush()
        return objs

    async def get_by_review(
        self,
        db: AsyncSession,
        review_id: int,
    ) -> List[Opinion]:
        """Get all opinions for a review."""
        result = await db.execute(
            select(Opinion)
            .where(Opinion.review_id == review_id)
            .order_by(Opinion.aspect)
        )
        return list(result.scalars().all())

    async def delete_for_reviews(
        self,
        db: AsyncSession,
        review_ids: list[int],
    ) -> int:
        """Delete all opinions for given review IDs (for re-extraction)."""
        if not review_ids:
            return 0
        result = await db.execute(
            delete(Opinion).where(Opinion.review_id.in_(review_ids))
        )
        await db.flush()
        return result.rowcount


opinion_crud = CRUDOpinion(Opinion)

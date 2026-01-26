"""CRUD operations for Consensus model."""

from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.consensus import Consensus
from app.schemas.common import Message


class ConsensusCreate(Message):
    """Schema for creating consensus (simplified)."""
    pass


class ConsensusUpdate(Message):
    """Schema for updating consensus (simplified)."""
    pass


class CRUDConsensus(CRUDBase[Consensus, ConsensusCreate, ConsensusUpdate]):
    """CRUD operations for Consensus model."""

    async def get_by_product(
        self,
        db: AsyncSession,
        product_id: int
    ) -> List[Consensus]:
        """Get all consensus data for a product."""
        result = await db.execute(
            select(Consensus)
            .where(Consensus.product_id == product_id)
            .order_by(Consensus.review_count.desc())
        )
        return list(result.scalars().all())

    async def get_by_product_and_aspect(
        self,
        db: AsyncSession,
        product_id: int,
        aspect: str
    ) -> Optional[Consensus]:
        """Get consensus for a specific product and aspect."""
        result = await db.execute(
            select(Consensus).where(
                and_(
                    Consensus.product_id == product_id,
                    Consensus.aspect == aspect
                )
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        db: AsyncSession,
        *,
        product_id: int,
        aspect: str,
        average_sentiment: float,
        agreement_score: float,
        review_count: int,
        details: Optional[dict] = None
    ) -> Consensus:
        """Create or update consensus data."""
        existing = await self.get_by_product_and_aspect(db, product_id, aspect)

        if existing:
            existing.average_sentiment = average_sentiment
            existing.agreement_score = agreement_score
            existing.review_count = review_count
            if details:
                existing.details = details
            db.add(existing)
            await db.flush()
            await db.refresh(existing)
            return existing
        else:
            consensus = Consensus(
                product_id=product_id,
                aspect=aspect,
                average_sentiment=average_sentiment,
                agreement_score=agreement_score,
                review_count=review_count,
                details=details or {}
            )
            db.add(consensus)
            await db.flush()
            await db.refresh(consensus)
            return consensus

    async def get_top_aspects(
        self,
        db: AsyncSession,
        product_id: int,
        limit: int = 5
    ) -> List[Consensus]:
        """Get top consensus aspects by review count."""
        result = await db.execute(
            select(Consensus)
            .where(Consensus.product_id == product_id)
            .order_by(Consensus.review_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


consensus_crud = CRUDConsensus(Consensus)

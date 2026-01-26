"""CRUD operations for Product model."""

from typing import List, Optional
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.product import Product
from app.models.consensus import Consensus
from app.models.review import Review
from app.schemas.product import ProductCreate, ProductUpdate


class CRUDProduct(CRUDBase[Product, ProductCreate, ProductUpdate]):
    """CRUD operations for Product model."""

    async def get_with_relations(
        self,
        db: AsyncSession,
        id: int
    ) -> Optional[Product]:
        """Get product with consensus and reviews loaded."""
        result = await db.execute(
            select(Product)
            .options(
                selectinload(Product.consensus_data),
                selectinload(Product.reviews).selectinload(Review.reviewer)
            )
            .where(Product.id == id)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        db: AsyncSession,
        *,
        query: str,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Product]:
        """Search products by name, brand, or model number."""
        search_term = f"%{query}%"

        stmt = select(Product).where(
            or_(
                Product.name.ilike(search_term),
                Product.brand.ilike(search_term),
                Product.model_number.ilike(search_term)
            )
        )

        if category:
            stmt = stmt.where(Product.category == category)

        stmt = stmt.order_by(Product.review_count.desc()).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_category(
        self,
        db: AsyncSession,
        *,
        category: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[Product]:
        """Get products by category."""
        result = await db.execute(
            select(Product)
            .where(Product.category == category)
            .order_by(Product.review_count.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_categories(self, db: AsyncSession) -> List[str]:
        """Get all unique categories."""
        result = await db.execute(
            select(Product.category).distinct().order_by(Product.category)
        )
        return list(result.scalars().all())

    async def update_review_stats(
        self,
        db: AsyncSession,
        product_id: int
    ) -> Optional[Product]:
        """Update review count and average rating for a product."""
        product = await self.get(db, id=product_id)
        if not product:
            return None

        # Count reviews
        count_result = await db.execute(
            select(func.count()).select_from(Review).where(Review.product_id == product_id)
        )
        review_count = count_result.scalar_one()

        # Calculate average rating
        avg_result = await db.execute(
            select(func.avg(Review.overall_rating))
            .where(Review.product_id == product_id)
            .where(Review.overall_rating.is_not(None))
        )
        avg_rating = avg_result.scalar_one()

        product.review_count = review_count
        product.average_rating = float(avg_rating) if avg_rating else None

        db.add(product)
        await db.flush()
        await db.refresh(product)
        return product


product_crud = CRUDProduct(Product)

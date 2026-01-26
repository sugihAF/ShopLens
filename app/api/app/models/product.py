"""Product model for tech products."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base, JSONB

if TYPE_CHECKING:
    from app.models.review import Review
    from app.models.consensus import Consensus
    from app.models.marketplace import MarketplaceListing


class Product(Base):
    """Product model representing tech products."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)

    # Specifications stored as JSONB for flexibility
    specifications: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Example specifications:
    # {
    #   "display": "6.7-inch OLED",
    #   "processor": "A17 Pro",
    #   "ram": "8GB",
    #   "storage": "256GB",
    #   "battery": "4422mAh"
    # }

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    official_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Aggregated stats
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Release info
    release_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now()
    )

    # Relationships
    reviews: Mapped[List["Review"]] = relationship(
        "Review",
        back_populates="product",
        cascade="all, delete-orphan"
    )
    consensus_data: Mapped[List["Consensus"]] = relationship(
        "Consensus",
        back_populates="product",
        cascade="all, delete-orphan"
    )
    marketplace_listings: Mapped[List["MarketplaceListing"]] = relationship(
        "MarketplaceListing",
        back_populates="product"
    )

    # Indexes for common queries
    __table_args__ = (
        Index('ix_products_category_brand', 'category', 'brand'),
        Index('ix_products_name_trgm', 'name'),  # For text search
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.name}, brand={self.brand})>"

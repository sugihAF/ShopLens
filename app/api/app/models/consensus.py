"""Consensus model for aggregated reviewer opinions."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base, JSONB

if TYPE_CHECKING:
    from app.models.product import Product


class Consensus(Base):
    """Consensus model representing aggregated opinions for a product aspect."""
    __tablename__ = "consensus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    aspect: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Example aspects: "camera", "battery", "display", "performance"

    # Consensus metrics
    average_sentiment: Mapped[float] = mapped_column(Float, nullable=False)
    # Range: -1.0 to 1.0 (average of all reviewer sentiments)

    agreement_score: Mapped[float] = mapped_column(Float, nullable=False)
    # Range: 0.0 to 1.0 (how much reviewers agree - low variance = high agreement)

    review_count: Mapped[int] = mapped_column(Integer, default=0)
    # Number of reviews contributing to this consensus

    # Additional details stored as JSONB
    details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Example details:
    # {
    #   "summary": "Most reviewers praise the camera quality...",
    #   "positive_points": ["excellent low light", "fast autofocus"],
    #   "negative_points": ["oversaturated colors"],
    #   "controversial": false,
    #   "outlier_reviewers": [5, 12],  # Reviewer IDs with significantly different opinions
    #   "sentiment_distribution": {"positive": 8, "neutral": 2, "negative": 1}
    # }

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
    product: Mapped["Product"] = relationship("Product", back_populates="consensus_data")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('product_id', 'aspect', name='uq_consensus_product_aspect'),
        Index('ix_consensus_product_sentiment', 'product_id', 'average_sentiment'),
    )

    def __repr__(self) -> str:
        return f"<Consensus(product_id={self.product_id}, aspect={self.aspect}, sentiment={self.average_sentiment:.2f})>"

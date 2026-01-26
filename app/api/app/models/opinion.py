"""Opinion model for extracted opinions from reviews."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.review import Review


class Opinion(Base):
    """Opinion model representing an extracted opinion from a review."""
    __tablename__ = "opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    review_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Opinion details
    aspect: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Example aspects: "camera", "battery", "display", "performance", "build_quality"

    sentiment: Mapped[float] = mapped_column(Float, nullable=False)
    # Range: -1.0 (very negative) to 1.0 (very positive)

    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # Range: 0.0 to 1.0 (how confident the AI is in this extraction)

    # Content
    quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Direct quote from the review supporting this opinion

    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Summarized version of the opinion

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    review: Mapped["Review"] = relationship("Review", back_populates="opinions")

    # Indexes
    __table_args__ = (
        Index('ix_opinions_review_aspect', 'review_id', 'aspect'),
        Index('ix_opinions_aspect_sentiment', 'aspect', 'sentiment'),
    )

    def __repr__(self) -> str:
        return f"<Opinion(id={self.id}, aspect={self.aspect}, sentiment={self.sentiment:.2f})>"

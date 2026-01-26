"""Review model for product reviews from reviewers."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List
import enum

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base, JSONB

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.reviewer import Reviewer
    from app.models.opinion import Opinion


class ReviewType(str, enum.Enum):
    """Type of review content."""
    FULL_REVIEW = "full_review"
    QUICK_LOOK = "quick_look"
    COMPARISON = "comparison"
    LONG_TERM = "long_term"
    UNBOXING = "unboxing"


class ProcessingStatus(str, enum.Enum):
    """Status of review processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Review(Base):
    """Review model representing a product review."""
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reviewers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Review content
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI-generated summary

    # Platform specific
    platform_url: Mapped[str] = mapped_column(String(500), unique=True)
    video_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # YouTube video ID

    # Review metadata
    review_type: Mapped[ReviewType] = mapped_column(
        Enum(ReviewType),
        default=ReviewType.FULL_REVIEW
    )
    overall_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0-10 scale

    # Additional metadata stored as JSONB
    review_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Example review_metadata:
    # {
    #   "duration_seconds": 900,
    #   "view_count": 500000,
    #   "like_count": 25000,
    #   "language": "en",
    #   "key_timestamps": [{"time": 120, "topic": "camera test"}]
    # }

    # Processing status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus),
        default=ProcessingStatus.PENDING
    )

    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="reviews")
    reviewer: Mapped["Reviewer"] = relationship("Reviewer", back_populates="reviews")
    opinions: Mapped[List["Opinion"]] = relationship(
        "Opinion",
        back_populates="review",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index('ix_reviews_product_reviewer', 'product_id', 'reviewer_id'),
        Index('ix_reviews_published_at', 'published_at'),
    )

    def __repr__(self) -> str:
        return f"<Review(id={self.id}, product_id={self.product_id}, reviewer_id={self.reviewer_id})>"

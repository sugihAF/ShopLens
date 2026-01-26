"""Reviewer model for trusted tech reviewers."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List
import enum

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base, JSONB

if TYPE_CHECKING:
    from app.models.review import Review


class Platform(str, enum.Enum):
    """Platform where reviewer publishes content."""
    YOUTUBE = "youtube"
    BLOG = "blog"
    PODCAST = "podcast"


class Reviewer(Base):
    """Reviewer model representing trusted tech reviewers."""
    __tablename__ = "reviewers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)

    # Platform-specific ID (e.g., YouTube channel ID)
    platform_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Profile information
    profile_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Credibility and stats
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)

    # Additional stats stored as JSONB
    stats: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Example stats:
    # {
    #   "avg_video_length": 900,
    #   "typical_categories": ["smartphones", "laptops"],
    #   "accuracy_score": 0.85,
    #   "engagement_rate": 0.05
    # }

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

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
        back_populates="reviewer"
    )

    def __repr__(self) -> str:
        return f"<Reviewer(id={self.id}, name={self.name}, platform={self.platform})>"

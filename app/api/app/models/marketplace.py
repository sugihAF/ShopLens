"""MarketplaceListing model for product availability and pricing."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Numeric, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base, JSONB

if TYPE_CHECKING:
    from app.models.product import Product


class MarketplaceListing(Base):
    """MarketplaceListing model for product availability across marketplaces.

    NOTE: This model matches the actual database schema which uses different
    column names than the original design.
    """
    __tablename__ = "marketplace_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Marketplace info - matches actual DB columns
    marketplace_name: Mapped[str] = mapped_column(String(100), nullable=False)
    country_code: Mapped[str] = mapped_column(String(10), nullable=False, default="US")

    # Seller info
    seller_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seller_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    seller_rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)

    # Listing details
    listing_url: Mapped[str] = mapped_column(String(512), nullable=False)

    # Pricing
    price_current: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    price_original: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="USD")

    # Availability
    is_available: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    shipping_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Additional metadata
    listing_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Timestamps
    last_checked: Mapped[Optional[datetime]] = mapped_column(
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

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="marketplace_listings"
    )

    # Indexes - match actual DB indexes
    __table_args__ = (
        Index('ix_marketplace_listings_product_country', 'product_id', 'country_code'),
    )

    def __repr__(self) -> str:
        return f"<MarketplaceListing(product_id={self.product_id}, marketplace={self.marketplace_name}, price={self.price_current})>"

    # Property aliases for compatibility with existing code
    @property
    def marketplace(self) -> str:
        """Alias for marketplace_name for code compatibility."""
        return self.marketplace_name

    @property
    def country(self) -> str:
        """Alias for country_code for code compatibility."""
        return self.country_code

    @property
    def url(self) -> str:
        """Alias for listing_url for code compatibility."""
        return self.listing_url

    @property
    def price(self) -> Optional[Decimal]:
        """Alias for price_current for code compatibility."""
        return self.price_current

    @property
    def original_price(self) -> Optional[Decimal]:
        """Alias for price_original for code compatibility."""
        return self.price_original

    @property
    def last_checked_at(self) -> Optional[datetime]:
        """Alias for last_checked for code compatibility."""
        return self.last_checked

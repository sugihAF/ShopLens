"""MarketplaceListing model for product availability and pricing."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
import enum

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base, JSONB

if TYPE_CHECKING:
    from app.models.product import Product


class Marketplace(str, enum.Enum):
    """Supported marketplaces."""
    AMAZON = "amazon"
    TOKOPEDIA = "tokopedia"
    SHOPEE = "shopee"
    BUKALAPAK = "bukalapak"
    BLIBLI = "blibli"
    LAZADA = "lazada"
    OFFICIAL = "official"  # Official brand store


class AvailabilityStatus(str, enum.Enum):
    """Product availability status."""
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    PRE_ORDER = "pre_order"
    UNKNOWN = "unknown"


class MarketplaceListing(Base):
    """MarketplaceListing model for product availability across marketplaces."""
    __tablename__ = "marketplace_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Marketplace info
    marketplace: Mapped[Marketplace] = mapped_column(
        Enum(Marketplace),
        nullable=False,
        index=True
    )
    country: Mapped[str] = mapped_column(String(2), default="ID", index=True)  # ISO country code

    # Listing details
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    affiliate_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Pricing
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IDR")  # ISO currency code
    original_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Before discount

    # Availability
    availability: Mapped[AvailabilityStatus] = mapped_column(
        Enum(AvailabilityStatus),
        default=AvailabilityStatus.UNKNOWN
    )

    # Additional metadata
    listing_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    # Example listing_metadata:
    # {
    #   "seller_name": "Official Store",
    #   "seller_rating": 4.8,
    #   "shipping_estimate": "2-3 days",
    #   "discount_percentage": 10
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
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="marketplace_listings"
    )

    # Indexes
    __table_args__ = (
        Index('ix_marketplace_product_marketplace', 'product_id', 'marketplace', 'country'),
        Index('ix_marketplace_price', 'product_id', 'price'),
    )

    def __repr__(self) -> str:
        return f"<MarketplaceListing(product_id={self.product_id}, marketplace={self.marketplace}, price={self.price})>"

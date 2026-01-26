"""Product-related schemas."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    """Base product schema."""
    model_config = {"protected_namespaces": ()}

    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    brand: Optional[str] = Field(None, max_length=100)
    model_number: Optional[str] = Field(None, max_length=100)
    specifications: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    official_url: Optional[str] = None


class ProductCreate(ProductBase):
    """Schema for creating a product."""
    pass


class ProductUpdate(BaseModel):
    """Schema for updating a product."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    brand: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    image_url: Optional[str] = None


class ProductResponse(ProductBase):
    """Product response schema."""
    model_config = {"protected_namespaces": (), "from_attributes": True}

    id: int
    review_count: int = 0
    average_rating: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class ConsensusAspect(BaseModel):
    """Consensus data for a single aspect."""
    aspect: str
    average_sentiment: float = Field(..., ge=-1, le=1)
    agreement_score: float = Field(..., ge=0, le=1)
    review_count: int
    summary: Optional[str] = None


class ReviewSummary(BaseModel):
    """Summary of a review for product detail."""
    id: int
    reviewer_name: str
    reviewer_platform: str
    title: Optional[str]
    overall_rating: Optional[float]
    published_at: Optional[datetime]
    platform_url: str


class ProductDetail(ProductResponse):
    """Detailed product view with reviews and consensus."""
    consensus_summary: List[ConsensusAspect] = []
    recent_reviews: List[ReviewSummary] = []


class ProductSearchResult(BaseModel):
    """Product search result."""
    id: int
    name: str
    category: str
    brand: Optional[str]
    review_count: int
    average_rating: Optional[float]
    image_url: Optional[str]
    relevance_score: Optional[float] = None

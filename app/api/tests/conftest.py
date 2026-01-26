"""Pytest configuration and fixtures for ShopLens API tests."""

import asyncio
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings
# Import all models to ensure they are registered with Base.metadata
from app.models import User, Product, Reviewer, Review, Opinion, Consensus, Conversation, Message, MarketplaceListing

# Test database URL - use SQLite for tests
# Using StaticPool ensures all connections share the same in-memory database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create a shared test engine for the entire session
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=StaticPool,
    echo=False,
    connect_args={"check_same_thread": False},
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()

    # Drop all tables after each test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test HTTP client."""
    from app.main import create_application
    from contextlib import asynccontextmanager

    # Create app without the lifespan that connects to production database
    @asynccontextmanager
    async def test_lifespan(app):
        yield

    test_app = create_application()
    test_app.router.lifespan_context = test_lifespan

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    test_app.dependency_overrides.clear()


@pytest.fixture
def mock_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
    }


@pytest.fixture
def mock_product_data():
    """Sample product data for testing."""
    return {
        "name": "iPhone 15 Pro",
        "brand": "Apple",
        "category": "smartphones",
        "model_number": "A2848",
        "description": "Latest iPhone with A17 Pro chip",
        "specifications": {
            "display": "6.1-inch Super Retina XDR",
            "chip": "A17 Pro",
            "storage": ["128GB", "256GB", "512GB", "1TB"],
        },
    }


@pytest.fixture
def mock_reviewer_data():
    """Sample reviewer data for testing."""
    return {
        "name": "MKBHD",
        "platform": "youtube",
        "channel_name": "Marques Brownlee",
        "channel_url": "https://youtube.com/@mkbhd",
        "channel_id": "UCBJycsmduvYEL83R_U4JriQ",
        "subscriber_count": 18000000,
        "country": "US",
        "language": "en",
        "expertise": ["smartphones", "laptops", "tech"],
        "trust_score": 0.95,
    }

"""
Test configuration and fixtures.
"""
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings

# Convert sync DATABASE_URL to async
async_database_url = settings.database_url.replace(
    "postgresql+psycopg2://", 
    "postgresql+asyncpg://"
).replace(
    "postgresql://",
    "postgresql+asyncpg://"
)

# Test engine
test_engine = create_async_engine(async_database_url, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session():
    """Provide database session for tests."""
    async with TestSessionLocal() as session:
        yield session

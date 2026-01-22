"""
Database connection and session management using SQLAlchemy async.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# Convert postgres:// to postgresql+asyncpg://
database_url = settings.database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

# Create async engine
engine = create_async_engine(
    database_url,
    echo=settings.is_development,  # SQL logging in dev mode
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Declarative base for ORM models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    Dependency for FastAPI endpoints to get database session.
    Usage:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables (optional - use schema.sql instead)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


"""
Canonical Database Module for Production
"""
import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Logger setup
logger = logging.getLogger("db")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

DATABASE_URL = settings.DATABASE_URL

# Fail fast if no DB URL (config.py already validates for prod, but double-check here)
if not DATABASE_URL:
    error_msg = "DATABASE_URL is not set. Set it in .env or environment variables."
    logger.error(f"CRITICAL: {error_msg}")
    raise ValueError(error_msg)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

import os
import sys
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from app.db import Base, engine
from app.models import Course, SearchQuery, Plan, PlanWeek, PlanItem

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("init_db")

def main():
    load_dotenv()
    
    try:
        # 1. Ensure ALL tables exist (including ChatSession, ChatMessage)
        # Check if tables exist first to give useful feedback, but rely on create_all
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        logger.info(f"Existing tables: {existing_tables}")
        
        logger.info("Running Base.metadata.create_all(engine)...")
        Base.metadata.create_all(bind=engine)
        logger.info("PASS: All missing tables created.")

        # 2. Ensure column courses.url exists
        columns = [c["name"] for c in inspector.get_columns("courses")]
        if "url" not in columns:
            logger.info("Adding column 'url' to 'courses' table...")
            try:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE courses ADD COLUMN url TEXT"))
                    conn.commit()
                logger.info("PASS: Column 'url' added to 'courses'.")
            except Exception as e:
                logger.error(f"FAIL: Could not add column 'url'. Reason: {e}")
                sys.exit(1)
        else:
            logger.info("PASS: Column 'url' already exists in 'courses'.")

        logger.info("\n✔ DB OK")
        
    except Exception as e:
        logger.error(f"FAIL: Database initialization failed. Reason: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

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
        # 1. Ensure tables exist
        inspector = inspect(engine)
        tables = ["courses", "search_queries", "plans", "plan_weeks", "plan_items"]
        
        for table in tables:
            if not inspector.has_table(table):
                logger.info(f"Creating table: {table}")
                try:
                    # Create specifically this table
                    if table == "courses": Course.__table__.create(engine)
                    elif table == "search_queries": SearchQuery.__table__.create(engine)
                    elif table == "plans": Plan.__table__.create(engine)
                    elif table == "plan_weeks": PlanWeek.__table__.create(engine)
                    elif table == "plan_items": PlanItem.__table__.create(engine)
                    logger.info(f"PASS: Table {table} created.")
                except Exception as e:
                    logger.error(f"FAIL: Could not create table {table}. Reason: {e}")
                    sys.exit(1)
            else:
                logger.info(f"PASS: Table {table} already exists.")

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

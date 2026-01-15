import os
import sys
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from app.db import engine

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("db_smoke_test")

def main():
    load_dotenv()
    
    try:
        # 1. Verify tables via information_schema (using inspector)
        inspector = inspect(engine)
        required_tables = ["courses", "search_queries", "plans", "plan_weeks", "plan_items"]
        existing_tables = inspector.get_table_names()
        
        for table in required_tables:
            if table in existing_tables:
                logger.info(f"PASS: Table '{table}' found.")
            else:
                logger.error(f"FAIL: Table '{table}' NOT found.")
                sys.exit(1)
        
        # 2. Verify courses table is writable
        logger.info("Verifying 'courses' table writability...")
        with engine.begin() as conn:
            # Insert a dummy row with a high row_idx to avoid conflicts (UPSERT would be better but let's just test write)
            # Use negative row_idx for test rows if possible, or just a very high one
            conn.execute(text("""
                INSERT INTO courses (row_idx, title, description) 
                VALUES (-1, 'SMOKE_TEST_TITLE', 'SMOKE_TEST_DESC')
                ON CONFLICT (row_idx) DO UPDATE SET title = EXCLUDED.title
            """))
            # Then delete it
            conn.execute(text("DELETE FROM courses WHERE row_idx = -1"))
        logger.info("PASS: 'courses' table is writable.")
        
        logger.info("\n✔ DB SMOKE TEST PASSED")
        
    except Exception as e:
        logger.error(f"FAIL: DB Smoke Test failed. Reason: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

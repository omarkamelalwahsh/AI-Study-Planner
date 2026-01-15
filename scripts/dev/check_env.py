import logging
import sys
from app.core.config import settings
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("check_env")

def main():
    # settings will automatically validate required vars or use defaults
    db_url = settings.DATABASE_URL
    
    # 2. Check DB Connection
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("PASS: Database connection successful (SELECT 1)")
    except Exception as e:
        logger.error(f"FAIL: Database connection failed. Reason: {e}")
        sys.exit(1)
        
    logger.info("PASS: All environment checks passed.")

if __name__ == "__main__":
    main()

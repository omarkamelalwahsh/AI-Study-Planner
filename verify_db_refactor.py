
import sys
import os
import uuid
import logging

# Add current dir to path so we can import app
sys.path.append(os.getcwd())

from app.db import engine, get_db, SessionLocal, DATABASE_URL
from app.models import ChatSession, ChatMessage
from app.services.chat_service import ChatService
from app.core.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verifier")

def test_db_connection():
    try:
        logger.info(f"Target DB URL from settings: {settings.DATABASE_URL}")
        logger.info(f"Engine URL: {engine.url}")
        
        # Security check: ensure we are NOT connecting as 'postgres' unless configured to
        if "postgres://" in str(engine.url) or "postgresql://" in str(engine.url):
             if "career_user" in str(engine.url):
                 logger.info("✅ Connection user seems correct (career_user).")
             else:
                 logger.warning("⚠️ Connection user might NOT be career_user. Check if this is intended.")
        
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT 1"))
            logger.info("✅ SELECT 1 success.")
            
    except Exception as e:
        logger.error(f"❌ DB Connection failed: {e}")
        sys.exit(1)

def test_chat_persistence():
    db = SessionLocal()
    try:
        # Dummy data
        session_id = str(uuid.uuid4())
        logger.info(f"Testing persistence with Session ID: {session_id}")
        
        # 1. Ensure Session
        # Check if we can instantiate service (needs mock path for CSV or exists)
        csv_path = os.path.join(os.getcwd(), "data", "courses.csv")
        # create valid dummy csv if missing
        if not os.path.exists(csv_path):
             os.makedirs(os.path.dirname(csv_path), exist_ok=True)
             with open(csv_path, "w", encoding="utf-8") as f:
                 f.write("course_name,category,url\nTest Course,General,http://test")
        
        service = ChatService(csv_path)
        
        s_obj = service.ensure_session(db, session_id)
        assert s_obj.id == uuid.UUID(session_id)
        logger.info("✅ ensure_session success.")
        
        # 2. Persist User Message
        msg = service.persist_user_message(db, session_id, "Hello Test")
        assert msg.id is not None
        assert msg.content == "Hello Test"
        logger.info("✅ persist_user_message success.")
        
        # 3. Verify in DB
        ver_s = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        ver_m = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).first()
        
        if ver_s and ver_m:
            logger.info(f"✅ Verified data in DB: Session Title='{ver_s.title}', Msg='{ver_m.content}'")
        else:
            logger.error("❌ Failed to verify data in DB.")
            
    except Exception as e:
        logger.exception(f"❌ Persistence test failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_db_connection()
    test_chat_persistence()

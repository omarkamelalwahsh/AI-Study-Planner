
import sys
import os
from sqlalchemy import create_engine, text
from app.core.config import settings

def check_messages():
    try:
        url = settings.DATABASE_URL
        print(f"Connecting to: {url}")
        engine = create_engine(url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT session_id, role, content FROM chat_messages ORDER BY created_at DESC LIMIT 5"))
            print("\n--- Recent Messages ---")
            for row in result:
                print(f"Session: {row.session_id} | Role: {row.role} | Content: {row.content[:50]}...")
            print("-----------------------")
    except Exception as e:
        print(f"SQL Check Failed: {e}")

if __name__ == "__main__":
    check_messages()

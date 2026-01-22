import asyncio
import os
import sys
from sqlalchemy import text
from app.database import engine

async def add_column():
    print("Adding session_memory column to chat_sessions table...")
    async with engine.begin() as conn:
        try:
            # Check if column exists first? 
            # Or just try to add it. Postres allows "ADD COLUMN IF NOT EXISTS"
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS session_memory JSONB DEFAULT '{}'"))
            print("Column added successfully or already exists.")
        except Exception as e:
            print(f"Error adding column: {e}")

if __name__ == "__main__":
    # Add project root to path
    sys.path.append(os.getcwd())
    asyncio.run(add_column())

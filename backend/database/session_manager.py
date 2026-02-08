"""
Career Copilot RAG Backend - Database Session Manager
Handles async database connections and session persistence.
"""
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from config import DATABASE_URL

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.engine = None
        self.async_session = None

    async def initialize(self):
        """Initialize the database engine and create/verify tables."""
        try:
            self.engine = create_async_engine(DATABASE_URL, echo=False, future=True)
            self.async_session = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
            
            # Create tables and verify schema
            async with self.engine.begin() as conn:
                # 1. Ensure chat_sessions exists with correct columns
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id VARCHAR(255) PRIMARY KEY,
                        session_memory JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                
                # Verify columns for existing tables (Production Fix)
                try:
                    # 1. Try to rename session_id to id if it exists (Legacy Support)
                    await conn.execute(text("""
                        DO $$ 
                        BEGIN 
                            IF EXISTS (SELECT 1 FROM information_schema.columns 
                                       WHERE table_name='chat_sessions' AND column_name='session_id') THEN
                                ALTER TABLE chat_sessions RENAME COLUMN session_id TO id;
                            END IF;
                        END $$;
                    """))
                    
                    # 2. Add id if it still doesn't exist
                    await conn.execute(text('ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS id VARCHAR(255)'))
                    
                    # 3. Ensure id is PRIMARY KEY
                    try:
                        await conn.execute(text("ALTER TABLE chat_sessions ADD PRIMARY KEY (id)"))
                    except Exception:
                        pass # Likely already has a PK
                except Exception as e:
                    logger.error(f"Failed to repair chat_sessions columns: {e}")

                try:
                    # Add session_memory if missing
                    await conn.execute(text('ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS session_memory JSONB DEFAULT \'{}\''))
                except Exception as e:
                    logger.error(f"Failed to add session_memory column: {e}")

                # 2. Ensure chat_messages exists
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(255) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                        role VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
            logger.info("Database engine initialized and schema verified.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """Retrieve session state from DB. Returns empty dict if not found."""
        if not self.async_session:
             logger.warning("DB not initialized, returning empty state")
             return {}

        async with self.async_session() as session:
            try:
                result = await session.execute(
                    text("SELECT session_memory FROM chat_sessions WHERE id = :sid"),
                    {"sid": session_id}
                )
                row = result.fetchone()
                if row and row[0]:
                    return row[0] if isinstance(row[0], dict) else json.loads(row[0])
                return {}
            except Exception as e:
                logger.error(f"Failed to get session state: {e}")
                return {}

    async def update_session_state(self, session_id: str, state: Dict[str, Any]):
        """Upsert session state."""
        if not self.async_session:
            return

        async with self.async_session() as session:
            try:
                # Upsert logic (PostgreSQL dependent)
                state_json = json.dumps(state)
                # Check if exists
                exists = await session.execute(
                    text("SELECT 1 FROM chat_sessions WHERE id = :sid"),
                    {"sid": session_id}
                )
                if exists.fetchone():
                    await session.execute(
                        text("UPDATE chat_sessions SET session_memory = :mem, updated_at = NOW() WHERE id = :sid"),
                        {"mem": state_json, "sid": session_id}
                    )
                else:
                    await session.execute(
                        text("INSERT INTO chat_sessions (id, session_memory) VALUES (:sid, :mem)"),
                        {"sid": session_id, "mem": state_json}
                    )
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to update session state: {e}")
                await session.rollback()

    async def add_message(self, session_id: str, role: str, content: str, metadata: Dict = None):
        """Add a message to the chat_messages table."""
        if not self.async_session:
            return

        async with self.async_session() as session:
            try:
                # Ensure session exists first
                # Check if exists
                exists = await session.execute(
                    text("SELECT 1 FROM chat_sessions WHERE id = :sid"),
                    {"sid": session_id}
                )
                if not exists.fetchone():
                    await session.execute(
                        text("INSERT INTO chat_sessions (id, session_memory) VALUES (:sid, '{}')"),
                        {"sid": session_id}
                    )
                
                # Insert message
                meta_json = json.dumps(metadata or {})
                await session.execute(
                    text("""
                        INSERT INTO chat_messages (session_id, role, content, metadata) 
                        VALUES (:sid, :role, :content, :meta)
                    """),
                    {"sid": session_id, "role": role, "content": content, "meta": meta_json}
                )
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to add message: {e}")
                await session.rollback()

    async def get_messages(self, session_id: str, limit: int = 10) -> list:
        """Retrieve recent messages."""
        if not self.async_session:
            return []

        async with self.async_session() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT role, content, metadata, created_at 
                        FROM chat_messages 
                        WHERE session_id = :sid 
                        ORDER BY created_at DESC 
                        LIMIT :lim
                    """),
                    {"sid": session_id, "lim": limit}
                )
                rows = result.fetchall()
                # Return in chronological order
                return list(reversed([
                    {"role": r[0], "content": r[1], "metadata": r[2], "timestamp": r[3]} 
                    for r in rows
                ]))
            except Exception as e:
                logger.error(f"Failed to get messages: {e}")
                return []

# Global instance
session_manager = SessionManager()

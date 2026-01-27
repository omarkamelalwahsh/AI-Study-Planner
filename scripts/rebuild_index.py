"""
Master Index Rebuild Script (Enterprise RAG)
Runs all ingestion steps in order:
1. Courses (CSV -> DB + FAISS)
2. Docs (PDF/Txt -> DB + FAISS) - Placeholder for future
3. Sanity Check
"""
import sys
import asyncio
import logging
from pathlib import Path

# Setup Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ingest_courses import main as ingest_courses_main
# from scripts.ingest_docs import main as ingest_docs_main

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rebuild_index")

async def main():
    logger.info("🚀 Starting Master Index Rebuild...")
    
    # 1. Ingest Courses
    try:
        logger.info("\n>>> STEP 1: Ingesting Courses")
        await ingest_courses_main()
    except Exception as e:
        logger.error(f"❌ Course ingestion failed: {e}")
        sys.exit(1)
        
    # 2. Ingest Docs (Future)
    # try:
    #     logger.info("\n>>> STEP 2: Ingesting Documents (Skipped - Ops Only)")
    #     # await ingest_docs_main()
    # except Exception as e:
    #     logger.error(f"❌ Doc ingestion failed: {e}")
        
    logger.info("\n✅ Index Rebuild Complete successfully.")

if __name__ == "__main__":
    asyncio.run(main())

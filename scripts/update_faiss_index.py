import sys
import os
import json
import logging
import numpy as np
import faiss
import argparse
from datetime import datetime

# Add project root
sys.path.append(os.getcwd())

from app.db import SessionLocal
from app.models import Course
from app.search.embedding import get_embedding
from scripts.build_faiss_index import build_course_index_text, DATA_DIR, INDEX_PATH, META_PATH

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_index(since_id: int = 0):
    """
    Add courses with ID > since_id to the existing index.
    """
    if not os.path.exists(INDEX_PATH) or not os.path.exists(META_PATH):
        logger.error("Existing index not found. Please run build_faiss_index.py first.")
        return

    # Load existing
    logger.info("Loading existing index/meta...")
    index = faiss.read_index(INDEX_PATH)
    with open(META_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    current_count = index.ntotal
    logger.info(f"Current index size: {current_count}")

    # Fetch new courses
    db = SessionLocal()
    try:
        # Assuming ID matches insertion order or we just fetch all and check?
        # Better: Filter by ID > max_id_in_meta? 
        # But metadata usage uses faiss_id as key.
        # Let's verify which course IDs are in metadata.
        existing_course_ids = set()
        for v in metadata.values():
            existing_course_ids.add(int(v["id"]))
        
        if since_id > 0:
            # explicit override
            new_courses = db.query(Course).filter(Course.id > since_id).all()
        else:
            # Auto-detect: fetch all and skip existing
            # (Not efficient for huge DB, but OK for this app)
            all_courses = db.query(Course).all()
            new_courses = [c for c in all_courses if c.id not in existing_course_ids]

        if not new_courses:
            logger.info("No new courses to add.")
            return

        logger.info(f"Found {len(new_courses)} new courses to add.")
        
        vectors = []
        new_metadata_entries = {}
        
        # Next faiss id
        next_id = current_count
        
        for c in new_courses:
            text = build_course_index_text(c)
            emb = get_embedding(text)
            
            if emb is not None:
                vectors.append(emb)
                
                new_metadata_entries[str(next_id)] = {
                    "id": str(c.id),
                    "title": c.title,
                    "category": c.category,
                    "level": c.level,
                    "skills": c.skills,
                    "url": c.url,
                    "duration_hours": c.duration_hours
                }
                next_id += 1
            else:
                logger.warning(f"Skipping course {c.id} due to embedding failure.")

        if vectors:
            vectors_np = np.array(vectors, dtype="float32")
            faiss.normalize_L2(vectors_np)
            
            # Add to index
            index.add(vectors_np)
            logger.info(f"Added {len(vectors)} vectors. New total: {index.ntotal}")
            
            # Update metadata
            metadata.update(new_metadata_entries)
            
            # Save
            faiss.write_index(index, INDEX_PATH)
            with open(META_PATH, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.info("Index and metadata updated successfully.")
        
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--since_id", type=int, default=0, help="Course ID to start from")
    args = parser.parse_args()
    
    update_index(args.since_id)

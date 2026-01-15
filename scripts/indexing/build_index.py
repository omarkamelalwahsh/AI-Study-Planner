import sys
import os
import json
import logging
import numpy as np
import faiss

# Add project root
sys.path.append(os.getcwd())

from app.db import SessionLocal
from app.models import Course
from app.search.embedding import get_embedding

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = os.path.join(os.getcwd(), "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

INDEX_PATH = os.path.join(DATA_DIR, "faiss.index")
META_PATH = os.path.join(DATA_DIR, "index_meta.json")

def build_course_index_text(course: Course) -> str:
    """
    Construct the full text representation for embedding.
    """
    # Defensive checks for None
    title = course.title or ""
    category = course.category or ""
    level = course.level or ""
    skills = course.skills or "" 
    desc = course.description or ""
    instructor = getattr(course, "instructor", "") or ""

    text = f"""Title: {title}
Category: {category}
Level: {level}
Skills: {skills}
Description: {desc}
Instructor: {instructor}"""
    return text.strip()

def build_index():
    db = SessionLocal()
    try:
        courses = db.query(Course).all()
        logger.info(f"Found {len(courses)} courses in DB.")

        vectors = []
        metadata = {}
        
        # We track faiss_id -> metadata
        # faiss_id will be the index in the 'vectors' list
        
        valid_count = 0
        for i, course in enumerate(courses):
            text_to_embed = build_course_index_text(course)
            
            emb = get_embedding(text_to_embed, embedding_type="passage")
            if emb is not None:
                vectors.append(emb)
                
                # Metadata to store
                metadata[str(valid_count)] = {
                    "id": str(course.id),
                    "title": course.title,
                    "category": course.category,
                    "level": course.level,
                    "skills": course.skills,
                    "url": course.url,
                    "duration_hours": course.duration_hours,
                    # We usually don't need description in search result metadata to save space,
                    # but can add if UI needs snippet.
                }
                valid_count += 1
            else:
                logger.warning(f"Failed to embed course {course.id}: {course.title}")

        if not vectors:
            logger.error("No vectors generated. Exiting.")
            return

        # Convert to float32 numpy array
        vectors_np = np.array(vectors, dtype="float32")
        
        # Normalize for Cosine Similarity (IndexFlatIP)
        faiss.normalize_L2(vectors_np)
        
        dimension = vectors_np.shape[1]
        logger.info(f"Building IndexFlatIP with dimension {dimension}...")
        
        index = faiss.IndexFlatIP(dimension)
        index.add(vectors_np)
        
        logger.info(f"Index built with {index.ntotal} vectors.")
        
        # Save Index
        faiss.write_index(index, INDEX_PATH)
        logger.info(f"Saved index to {INDEX_PATH}")
        
        # Save Metadata
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved metadata to {META_PATH}")

    except Exception as e:
        logger.error(f"Build failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    build_index()

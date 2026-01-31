"""
Script to rebuild the FAISS index with correct passage: prefixes for multilingual-e5.
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import faiss
import pickle
import logging
from sentence_transformers import SentenceTransformer
from config import COURSES_CSV, DATA_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMBED_MODEL_NAME = "intfloat/multilingual-e5-small"
INDEX_DIR = DATA_DIR / "faiss_index" / "index.faiss"
INDEX_PATH = INDEX_DIR / "courses.faiss"
MAPPING_PATH = INDEX_DIR / "id_mapping.pkl"

def rebuild_index():
    logger.info("Starting index rebuild...")
    
    if not COURSES_CSV.exists():
        logger.error(f"Courses CSV not found at {COURSES_CSV}")
        return
    
    df = pd.read_csv(COURSES_CSV)
    logger.info(f"Loaded {len(df)} courses")
    
    model = SentenceTransformer(EMBED_MODEL_NAME)
    
    passages = []
    course_ids = []
    
    for _, row in df.iterrows():
        title = str(row.get('title', ''))
        # description column might be named 'description_full' or 'description'
        desc = str(row.get('description_full') or row.get('description_short') or row.get('description') or '')
        cat = str(row.get('category', ''))
        
        # Multilingual-E5 requires "passage: " prefix for document embeddings
        text = f"passage: {title} {cat} {desc}"
        passages.append(text)
        course_ids.append(str(row['course_id']))
    
    logger.info(f"Encoding {len(passages)} passages...")
    embeddings = model.encode(passages, normalize_embeddings=True, show_progress_bar=True)
    embeddings = embeddings.astype('float32')
    
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Inner Product (Cosine similarity since normalized)
    index.add(embeddings)
    
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    
    faiss.write_index(index, str(INDEX_PATH))
    with open(MAPPING_PATH, 'wb') as f:
        pickle.dump(course_ids, f)
        
    logger.info(f"Successfully rebuilt index at {INDEX_PATH}")

if __name__ == "__main__":
    rebuild_index()

import os
import sys

# Ensure the root directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import logging
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def build_role_kb_index():
    """
    Builds a FAISS index for the Role KB.
    """
    kb_path = "data/roles.jsonl"
    if not os.path.exists(kb_path):
        logger.error(f"KB file not found: {kb_path}")
        return

    roles = []
    with open(kb_path, "r", encoding="utf-8") as f:
        for line in f:
            roles.append(json.loads(line))

    if not roles:
        logger.warning("No roles found in KB.")
        return

    # Prepare texts for embedding
    # Combine role name and required skills for richer context
    texts = [f"Role: {r['role']} | Skills: {', '.join(r['required_skills'])}" for r in roles]

    logger.info(f"Embedding {len(texts)} roles using {settings.EMBED_MODEL_NAME}...")
    model = SentenceTransformer(settings.EMBED_MODEL_NAME)
    embeddings = model.encode(texts, normalize_embeddings=True)

    # Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings.astype('float32'))

    # Save index and metadata
    output_dir = "data/role_kb_index"
    os.makedirs(output_dir, exist_ok=True)
    
    faiss.write_index(index, os.path.join(output_dir, "role_kb.index"))
    
    with open(os.path.join(output_dir, "role_kb_meta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "model_name": settings.EMBED_MODEL_NAME,
            "count": len(roles),
            "dim": dim,
            "roles": roles
        }, f, indent=2)

    logger.info(f"Role KB Index built successfully in {output_dir}")

if __name__ == "__main__":
    build_role_kb_index()

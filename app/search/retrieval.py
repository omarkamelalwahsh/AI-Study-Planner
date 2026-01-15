import logging
import faiss
import json
import os
import numpy as np
from typing import List, Dict, Optional, Any

from app.search.embedding import get_embedding

logger = logging.getLogger(__name__)

# Paths
DATA_DIR = os.path.join(os.getcwd(), "data")
INDEX_PATH = os.path.join(DATA_DIR, "faiss.index")
META_PATH = os.path.join(DATA_DIR, "index_meta.json")

class SearchEngine:
    _index = None
    _metadata: Dict[str, Any] = {}
    _loaded = False

    @classmethod
    def load_index(cls):
        """
        Load FAISS index and metadata if not already loaded.
        """
        if cls._loaded and cls._index:
            return

        if not os.path.exists(INDEX_PATH) or not os.path.exists(META_PATH):
            logger.warning("FAISS index or metadata not found. Search will return empty.")
            return

        try:
            logger.info(f"Loading FAISS index from {INDEX_PATH}...")
            cls._index = faiss.read_index(INDEX_PATH)
            
            with open(META_PATH, "r", encoding="utf-8") as f:
                cls._metadata = json.load(f)
            
            cls._loaded = True
            logger.info(f"Index loaded. Size: {cls._index.ntotal}")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            cls._index = None
            cls._metadata = {}

    @classmethod
    def search(cls, query: str, top_k: int = 30) -> List[Dict[str, Any]]:
        """
        Dumb retriever:
        1. Embed query (ALWAYS).
        2. Search Index.
        3. Return mapped results with scores.
        """
        if not query or not query.strip():
            return []

        cls.load_index()
        if not cls._index:
            return []

        # 1. Embed
        vector = get_embedding(query)
        if vector is None:
            logger.warning("Embedding failed for query.")
            return []
            
        vector = np.array([vector], dtype="float32")
        faiss.normalize_L2(vector) # Ensure query is normalized for IP/Cosine

        # 2. Search
        # We ask for top_k results
        scores, indices = cls._index.search(vector, top_k)
        
        # 3. Map Results
        results = []
        # indices[0] is the list of neighbor IDs
        # scores[0] is the list of scores (cosine similarity if normalized)
        
        found_indices = indices[0]
        found_scores = scores[0]

        for i, idx in enumerate(found_indices):
            if idx == -1:
                continue
                
            idx_str = str(idx)
            if idx_str in cls._metadata:
                item = cls._metadata[idx_str]
                # Inject score
                item["score"] = float(found_scores[i])
                results.append(item)

        return results

    @classmethod
    def add_courses(cls, new_courses: List[dict]):
        """
        Add new courses to the running index (in-memory update).
        You should probably update the disk index via script properly,
        but this allows runtime updates if needed.
        """
        # Not implemented safe runtime update yet, separate script preferred.
        pass

"""
Career Copilot RAG Backend - FAISS Semantic Search
Uses FAISS vector index for semantic similarity search.
"""
import logging
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Try to import FAISS and sentence-transformers
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not installed. Semantic search disabled.")

try:
    from sentence_transformers import SentenceTransformer
    EMBED_AVAILABLE = True
except ImportError:
    EMBED_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Semantic search disabled.")

from config import DATA_DIR

FAISS_INDEX_PATH = DATA_DIR / "faiss_index" / "index.faiss" / "courses.faiss"
ID_MAPPING_PATH = DATA_DIR / "faiss_index" / "index.faiss" / "id_mapping.pkl"
EMBED_MODEL_NAME = "intfloat/multilingual-e5-small"


class SemanticSearch:
    """FAISS-based semantic search for courses."""
    
    def __init__(self):
        self.index = None
        self.id_mapping: List[str] = []
        self.embedder = None
        self._loaded = False
    
    def load(self) -> bool:
        """Load FAISS index and embedding model."""
        if not FAISS_AVAILABLE or not EMBED_AVAILABLE:
            logger.warning("Semantic search dependencies not available")
            return False
        
        try:
            # Load FAISS index
            if not FAISS_INDEX_PATH.exists():
                logger.warning(f"FAISS index not found: {FAISS_INDEX_PATH}")
                return False
            
            self.index = faiss.read_index(str(FAISS_INDEX_PATH))
            logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
            
            # Load ID mapping
            if ID_MAPPING_PATH.exists():
                with open(ID_MAPPING_PATH, 'rb') as f:
                    self.id_mapping = pickle.load(f)
                logger.info(f"Loaded {len(self.id_mapping)} ID mappings")
            
            # Load embedding model
            self.embedder = SentenceTransformer(EMBED_MODEL_NAME)
            logger.info(f"Loaded embedding model: {EMBED_MODEL_NAME}")
            
            self._loaded = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to load semantic search: {e}")
            return False
    
    SCORE_THRESHOLD = 0.7  # Minimum similarity score for a match
    
    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Search for similar courses using semantic similarity.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            List of (course_id, similarity_score) tuples
        """
        if not self._loaded:
            if not self.load():
                return []
        
        if not self.index or not self.embedder:
            return []
        
        try:
            # Embed query
            # For e5 models, prefix query with "query: "
            query_text = f"query: {query}"
            query_vector = self.embedder.encode([query_text], normalize_embeddings=True)
            
            # Search FAISS index
            scores, indices = self.index.search(query_vector.astype('float32'), top_k)
            
            # Map indices to course IDs
            results = []
            for idx, score in zip(indices[0], scores[0]):
                if idx < len(self.id_mapping) and idx >= 0:
                    # Filter by score
                    if score < self.SCORE_THRESHOLD:
                        continue
                    
                    course_id = self.id_mapping[idx]
                    results.append((course_id, float(score)))
            
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def is_available(self) -> bool:
        """Check if semantic search is available."""
        return FAISS_AVAILABLE and EMBED_AVAILABLE


# Global instance
semantic_search = SemanticSearch()

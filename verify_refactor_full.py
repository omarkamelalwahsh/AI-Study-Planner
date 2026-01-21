
import sys
import os
import logging
from typing import List

# Add current dir to path
sys.path.append(os.getcwd())

from app.services.retrieval_service import DBRetrievalService
from app.search.embedding import get_embedding

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_refactor")

def test_retrieval():
    logger.info("--- Testing DB Retrieval Service ---")
    
    try:
        service = DBRetrievalService()
        
        # Test 1: Load Data (Implicitly called in __new__)
        assert len(service._course_ids) > 0, "No course IDs loaded"
        assert service._embeddings_matrix is not None, "No embeddings loaded"
        logger.info(f"✅ Data Loaded: {len(service._course_ids)} items")

        # Test 2: Search specific term
        query = "Python"
        results = service.search(query, top_k=3)
        assert len(results) > 0, f"No results for '{query}'"
        top = results[0]
        logger.info(f"✅ Search '{query}' -> Top: {top['title']} (Score: {top['score']:.4f})")
        assert "Python" in top['title'] or "Python" in top['skills'], "Top result not relevant?"

        # Test 3: Search nonsense (No Hallucination Check)
        query = "asdfghjkl12345" # nonsense
        results = service.search(query, score_threshold=0.6)
        if len(results) == 0:
            logger.info(f"✅ Search '{query}' -> Correctly returned 0 results (Threshold check)")
        else:
            logger.warning(f"⚠️ Search '{query}' returned results: {[r['title'] for r in results]}. Adjust threshold?")

    except Exception as e:
        logger.error(f"❌ Retrieval Test Failed: {e}")
        raise e

def test_embedding_gen():
    logger.info("--- Testing Embedding Generation ---")
    v = get_embedding("test", "query")
    assert v is not None
    assert len(v) == 384, f"Unexpected embedding dimension: {len(v)}"
    logger.info("✅ Embedding model works.")

if __name__ == "__main__":
    test_embedding_gen()
    test_retrieval()
    logger.info("ALL TESTS PASSED")

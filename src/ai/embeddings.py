from sentence_transformers import SentenceTransformer, CrossEncoder
import numpy as np
from typing import List, Union
from src.config import EMBEDDING_MODEL_NAME, RERANKER_MODEL_NAME
from src.logger import setup_logger

logger = setup_logger(__name__)

class EmbeddingService:
    _instance = None
    _model = None
    _reranker = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def load_model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
            try:
                self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

    def load_reranker(self):
        """Lazy load the reranker model."""
        if self._reranker is None:
            logger.info(f"Loading reranker model: {RERANKER_MODEL_NAME}")
            try:
                self._reranker = CrossEncoder(RERANKER_MODEL_NAME, max_length=512)
            except Exception as e:
                logger.error(f"Failed to load reranker model: {e}")
                # Reranker is optional, so we might not raise depending on policy, 
                # but for now let's log error.
                pass

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        self.load_model()
        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings

    def rerank(self, query: str, candidates: List[str]) -> np.ndarray:
        self.load_reranker()
        if not self._reranker:
            return np.zeros(len(candidates)) # Fallback if reranker fails load
            
        pairs = [[query, c] for c in candidates]
        scores = self._reranker.predict(pairs)
        return scores

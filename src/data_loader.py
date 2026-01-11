import pandas as pd
import numpy as np
from typing import Tuple, Optional, Any

from src.config import FAISS_INDEX_PATH, CLEAN_DATA_PARQUET, EMBEDDINGS_PATH
from src.logger import setup_logger

logger = setup_logger(__name__)

# محاولة استيراد faiss
try:
    import faiss  # type: ignore
    _FAISS_AVAILABLE = True
except Exception:
    faiss = None  # type: ignore
    _FAISS_AVAILABLE = False

# Fallback: sklearn
from sklearn.neighbors import NearestNeighbors


class _SklearnIndexAdapter:
    """
    Adapter يقدّم نفس واجهة faiss الأساسية: search(query, k) -> (scores, indices)
    - scores هنا Similarity (1 - cosine_distance)
    """

    def __init__(self, embeddings: np.ndarray):
        if embeddings.ndim != 2:
            raise ValueError("Embeddings must be a 2D array of shape (n_items, dim).")

        # نحافظ على float32 لتكون مشابهة لـ faiss
        self.embeddings = embeddings.astype(np.float32, copy=False)

        self.nn = NearestNeighbors(metric="cosine", algorithm="auto")
        self.nn.fit(self.embeddings)

    def search(self, query: np.ndarray, k: int):
        q = np.asarray(query, dtype=np.float32)

        # faiss عادةً تتوقع (1, dim)
        if q.ndim == 1:
            q = q.reshape(1, -1)

        distances, indices = self.nn.kneighbors(q, n_neighbors=k)
        scores = 1.0 - distances  # cosine similarity تقريباً
        return scores.astype(np.float32), indices.astype(np.int64)


class DataLoader:
    _instance = None
    _index: Optional[Any] = None
    _courses_df: Optional[pd.DataFrame] = None
    _mode: Optional[str] = None  # "faiss" or "sklearn"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataLoader, cls).__new__(cls)
        return cls._instance

    def load_data(self) -> Tuple[Optional[Any], Optional[pd.DataFrame]]:
        """
        Load index + Courses DataFrame.
        Returns:
          index: faiss index OR sklearn adapter (both support .search(query, k))
          courses_df: dataframe
        """
        if self._index is not None and self._courses_df is not None:
            return self._index, self._courses_df

        # 1) حمل الداتا (مشروطة موجودة)
        try:
            logger.info("Loading Courses Parquet...")
            if not CLEAN_DATA_PARQUET.exists():
                logger.error(f"Data not found at {CLEAN_DATA_PARQUET}")
                return None, None

            self._courses_df = pd.read_parquet(CLEAN_DATA_PARQUET)
        except Exception as e:
            logger.error(f"Error loading parquet data: {e}")
            raise

        # 2) حاول FAISS أولاً
        if _FAISS_AVAILABLE:
            try:
                logger.info("FAISS is available. Loading FAISS index...")
                if not FAISS_INDEX_PATH.exists():
                    logger.warning(f"FAISS index not found at {FAISS_INDEX_PATH}. Will fallback to sklearn index.")
                else:
                    self._index = faiss.read_index(str(FAISS_INDEX_PATH))  # type: ignore
                    self._mode = "faiss"
                    logger.info("FAISS index loaded successfully.")
                    return self._index, self._courses_df
            except Exception as e:
                logger.warning(f"Failed to load FAISS index; falling back to sklearn. Reason: {e}")

        # 3) Fallback إلى sklearn باستخدام embeddings
        try:
            logger.info("Building sklearn fallback index from embeddings...")

            if not EMBEDDINGS_PATH.exists():
                logger.error(f"Embeddings file not found at {EMBEDDINGS_PATH}")
                return None, self._courses_df

            # نفترض أنه .npy
            embeddings = np.load(EMBEDDINGS_PATH)

            if not isinstance(embeddings, np.ndarray):
                raise ValueError("Loaded embeddings are not a numpy array.")

            # تحقق من تطابق عدد الصفوف مع الداتا
            if self._courses_df is not None and len(self._courses_df) != embeddings.shape[0]:
                logger.warning(
                    "Embeddings count does not match courses rows: "
                    f"courses={len(self._courses_df)} vs embeddings={embeddings.shape[0]}. "
                    "Search results indices may not align correctly."
                )

            self._index = _SklearnIndexAdapter(embeddings)
            self._mode = "sklearn"
            logger.info("Sklearn fallback index built successfully.")
            return self._index, self._courses_df

        except Exception as e:
            logger.error(f"Error building sklearn fallback index: {e}")
            raise

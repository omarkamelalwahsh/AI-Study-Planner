import os
from pathlib import Path

# Project Root
ROOT_DIR = Path(__file__).parent.parent.absolute()

# Data Paths
DATA_DIR = ROOT_DIR / "data"
COURSES_CSV = DATA_DIR / "courses.csv"
CLEAN_DATA_PARQUET = DATA_DIR / "courses_clean.parquet"
FAISS_INDEX_PATH = DATA_DIR / "faiss.index"
EMBEDDINGS_PATH = DATA_DIR / "course_embeddings.npy"

# Models
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Validation & Thresholds
# Validation & Thresholds
MIN_QUERY_LENGTH = 2
SEMANTIC_THRESHOLD_ARABIC = 0.25 # slightly lower for cross-lingual
SEMANTIC_THRESHOLD_GENERAL = 0.35 # Standard strictness
SEMANTIC_THRESHOLD_RELAXED = 0.22 # Fallback
TOP_K_DEFAULT = 10
TOP_K_Candidates = 100

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Zedny Smart Course Recommender

> **Principal Engineer Production Refactor**

A robust, production-grade semantic search and learning plan generator. All recommendations and plans are strictly grounded in the local dataset. No hallucinated content. Runs only on Python 3.11.

[Streamlit Documentation](https://docs.streamlit.io/)

---

## 🚀 Key Features
- **Strict Data-Only Contract:** All courses and plans are built only from the local dataset (CSV/Parquet). No invented content.
- **Progression Ordering:** Plans follow Beginner → Intermediate → Advanced order, based on dataset levels.
- **Hard Filters:** Sidebar filters (category/level) are true constraints.
- **No Results Handling:** If no dataset courses match, shows: `No relevant courses were found in our dataset for your request.`
- **Python 3.11 Enforcement:** App stops immediately if not running on Python 3.11.x.
- **Robust PDF Export:** PDF export is available only if safe; disables gracefully on Unicode/Arabic error.
- **No Duplicated UI:** Single, clear results and plan sections.

---

## 🏗️ Architecture

```
AI-Study-Planner/
├── app.py              # Streamlit UI (strict, data-only, robust)
├── main.py             # CLI entry (optional)
├── src/
│   ├── pipeline.py     # Recommendation pipeline (retrieval, filtering, ordering)
│   ├── data_loader.py  # Loads dataset (parquet/csv), validates columns
│   ├── planner.py      # Builds learning plan (progression, chunking)
│   ├── schemas.py      # Pydantic models (strict validation)
│   ├── config.py       # Paths, constants, model names
│   ├── utils.py        # Text normalization, helpers
│   └── ai/
│       ├── embeddings.py
│       ├── gating.py
│       └── ranker.py
├── data/
│   ├── courses.csv
│   ├── courses_clean.parquet
│   ├── faiss.index
│   └── course_embeddings.npy
├── scripts/
│   ├── build_index.py
│   └── preflight.py
├── tests/
│   ├── test_recommender.py
│   ├── test_relevance_v2.py
│   └── test_strict_arabic.py
├── requirements.txt
├── requirements-optional.txt
├── .gitignore
├── CONTRIBUTING.md
└── CHANGELOG.md
```

---

## 📦 Data Files & Alignment
- **courses_clean.parquet** (preferred) or **courses.csv**: Must contain at least: `title`, `url`, `level`, `category`.
- **course_embeddings.npy**: Row order must match the dataset exactly.
- **faiss.index**: Optional, for fast retrieval. Must match dataset row order.

---

## 🧠 Models Used
- **Embedding Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **(Optional) Reranker:** `cross-encoder/ms-marco-MiniLM-L-6-v2`

---

## ⚙️ Setup (Python 3.11 Only)

1. **Install Miniconda (Recommended):**
   https://docs.conda.io/en/latest/miniconda.html
2. **Create environment:**
   ```sh
   conda create -n zedny311 python=3.11
   conda activate zedny311
   ```
3. **Install requirements:**
   ```sh
   pip install -r requirements.txt
   # For FAISS on Windows, use conda:
   conda install -c conda-forge faiss-cpu
   ```
4. **Preflight check:**
   ```sh
   python scripts/preflight.py
   ```
5. **Build index (if needed):**
   ```sh
   python scripts/build_index.py
   ```
6. **Run app:**
   ```sh
   streamlit run app.py
   ```

---

## 🏃 Usage
- **Web UI:**
  ```sh
  streamlit run app.py
  ```
- **CLI:**
  ```sh
  python main.py "python" --top_k 5
  ```

---

## 🧪 Testing
- Run all tests:
  ```sh
  python -m pytest tests/
  ```

---

## 🛠️ Troubleshooting
| Error | Fix |
|-------|-----|
| `This application requires Python 3.11` | Create and activate a Python 3.11 environment |
| `Index missing` | Run `python scripts/build_index.py` |
| `ModuleNotFoundError` | Ensure you run from project root |
| `PDF export is unavailable` | Unicode/Arabic not supported in PDF; use Markdown download |
| `No relevant courses were found...` | No dataset match; check your query or dataset |
| FAISS not found (Windows) | Use `conda install -c conda-forge faiss-cpu` |
| Embeddings mismatch | Rebuild index and embeddings to match dataset |

---

## 📄 File Responsibilities
- **app.py:** Streamlit UI, strict data-only flow, robust error handling
- **src/pipeline.py:** Recommendation logic, hard filters, progression ordering
- **src/data_loader.py:** Loads/validates dataset, supports parquet/csv, logs errors
- **src/planner.py:** Builds plan from dataset-backed courses, no hallucinated content
- **src/schemas.py:** Strict Pydantic models for all data
- **src/config.py:** Paths, constants, model names
- **src/utils.py:** Text normalization, helpers
- **ai/**: Embedding, gating, and ranking logic
- **scripts/**: Index building, preflight checks
- **tests/**: Unit tests for pipeline and planner

---

## 🤝 Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md)

## 📜 Changelog
See [CHANGELOG.md](CHANGELOG.md)

---

**Version:** 2.0.0 (Production Refactor)
**Author:** Principal Engineer

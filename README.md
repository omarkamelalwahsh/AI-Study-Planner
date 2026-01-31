# Career Copilot RAG (Production V16)

A hardened, deterministic RAG backend for career guidance.
This system is designed to be **Data-Driven**: changing `data/courses.csv` immediately updates available tracks and categories without code changes.

## Production Checklist

1. **Verify Data Integrity**:
   - Ensure `data/courses.csv` exists and has valid `Category` column.
   - Run `python backend/tests/test_smoke_intents.py` to verify data loading.

2. **Run Backend**:

   ```bash
   uvicorn main:app --reload --port 8001
   ```

3. **Run Frontend**:

   ```bash
   npm run dev
   ```

4. **Sanity Checks**:
   - Ask: "ايه الكورسات المتاحة" -> Should return list of categories from CSV.
   - Ask: "ازاي ابقى مدير مبرمجين" -> Should map to Engineering Management track.
   - Ask: "courses in X" (where X is a real category) -> Should return courses.
   - Ask: "courses in Y" (where Y is FAKE) -> Should warn or fallback to General.

## Critical Files

- `backend/pipeline/track_resolver.py`: The brain of data-driven routing.
- `backend/data_loader.py`: The single source of truth for categories.
- `backend/main.py`: The pipeline orchestrator (Hard Reset logic).
- `backend/models.py`: Pydantic schemas (Safe defaults).

## Adding New Data

Simply update `data/courses.csv`. The system will automatically:

- Detect new categories.
- Update the "Catalog Browsing" list.
- Allow semantic search for the new domain.

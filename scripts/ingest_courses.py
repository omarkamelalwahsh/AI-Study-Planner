import os
import sys
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# Add root folder to path
sys.path.append(os.getcwd())

from app.search.embedding import get_embedding
from app.core.config import settings

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    settings.DATABASE_URL
)
CSV_PATH = "data/courses.csv"
MODEL_NAME = settings.EMBED_MODEL_NAME or "intfloat/multilingual-e5-small"

def norm(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    return s if s else None

def main():
    print(f"Connecting to DB: {DATABASE_URL}")
    # IMPORTANT: utf-8-sig removes BOM
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

    required = ["course_id", "title"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"Missing column in CSV: {c}. Found: {df.columns.tolist()}")

    df = df.reset_index(drop=True)
    df["row_idx"] = df.index.astype(int)

    course_rows = []
    embedding_rows = []

    print(f"Processing {len(df)} courses...")

    for _, r in df.iterrows():
        course_id = norm(r.get("course_id"))
        title = norm(r.get("title"))
        if not course_id or not title:
            continue

        desc = norm(r.get("description"))
        skills = norm(r.get("skills"))
        
        # Prepare search text for embedding
        # Unified text: title + skills + description
        search_text = f"{title or ''} {skills or ''} {desc or ''}".strip()
        
        # Generate embedding
        emb_vector = None
        if search_text:
            emb_vector = get_embedding(search_text, embedding_type="passage")
        
        # Record course data
        course_rows.append({
            "id": course_id,  # keep original UUID from CSV
            "row_idx": int(r["row_idx"]),
            "title": title,
            "description": desc,
            "category": norm(r.get("category")),
            "level": norm(r.get("level")),
            "duration_hours": float(r["duration_hours"]) if pd.notna(r.get("duration_hours")) else None,
            "skills": skills,
            "instructor": norm(r.get("instructor")),
            "cover": norm(r.get("cover")),
            "url": None,  # CSV doesn't have url column
        })

        # Record embedding data if valid
        if emb_vector is not None:
            # Convert numpy array to list for SQL insertion
            emb_list = emb_vector.tolist() if isinstance(emb_vector, np.ndarray) else emb_vector
            embedding_rows.append({
                "course_id": course_id,
                "model_name": MODEL_NAME,
                "embedding": emb_list
            })

    engine = create_engine(DATABASE_URL)

    with engine.begin() as conn:
        # optional reset while testing
        conn.execute(text("TRUNCATE TABLE course_embeddings RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE TABLE courses RESTART IDENTITY CASCADE"))

        print("Inserting courses...")
        conn.execute(text("""
            INSERT INTO courses (id, row_idx, title, description, category, level, duration_hours, skills, instructor, cover, url)
            VALUES (:id, :row_idx, :title, :description, :category, :level, :duration_hours, :skills, :instructor, :cover, :url)
        """), course_rows)
        
        if embedding_rows:
            print(f"Inserting {len(embedding_rows)} embeddings...")
            conn.execute(text("""
                INSERT INTO course_embeddings (course_id, model_name, embedding)
                VALUES (:course_id, :model_name, :embedding)
            """), embedding_rows)

    print(f"✅ Success! Inserted {len(course_rows)} courses and {len(embedding_rows)} embeddings.")

if __name__ == "__main__":
    main()

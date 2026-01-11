import os
import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def build_index():
    print("Starting Production Index Build...")
    
    # Configuration
    DATA_PATH = "data/courses.csv"
    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    OUTPUT_PARQUET = "data/courses_clean.parquet"
    OUTPUT_EMBEDDINGS = "data/course_embeddings.npy"
    OUTPUT_FAISS = "data/faiss.index"

    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        return

    # 1. Load dataset
    print(f"Loading dataset from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)

    # 2. Validate required columns
    required_cols = ['course_id', 'title', 'category', 'level', 'duration_hours', 'skills', 'description', 'instructor']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns: {missing_cols}")
        return
    
    # 3. Create combined_text
    # title + skills + description + category + level + instructor
    print("Creating combined text for embeddings...")
    df['combined_text'] = (
        df['title'].fillna('') + " " + 
        df['skills'].fillna('') + " " + 
        df['description'].fillna('') + " " + 
        df['category'].fillna('') + " " + 
        df['level'].fillna('') + " " + 
        df['instructor'].fillna('')
    ).str.lower()

    # 4. Compute embeddings
    print(f"Loading model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    print("Computing embeddings (this may take a few minutes)...")
    embeddings = model.encode(df['combined_text'].tolist(), show_progress_bar=True)
    embeddings = np.array(embeddings).astype('float32')

    # 5. Save artifacts
    print(f"Saving cleaned data to {OUTPUT_PARQUET}...")
    df.to_parquet(OUTPUT_PARQUET, index=False)

    print(f"Saving embeddings to {OUTPUT_EMBEDDINGS}...")
    np.save(OUTPUT_EMBEDDINGS, embeddings)

    print(f"Saving building and saving FAISS index to {OUTPUT_FAISS}...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Inner Product for cosine similarity (with normalized vectors)
    
    # Normalize embeddings for cosine similarity via Inner Product
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    faiss.write_index(index, OUTPUT_FAISS)

    print("Build Complete!")
    print(f"   - Parquet: {OUTPUT_PARQUET}")
    print(f"   - Embeddings: {OUTPUT_EMBEDDINGS}")
    print(f"   - FAISS Index: {OUTPUT_FAISS}")

if __name__ == "__main__":
    build_index()

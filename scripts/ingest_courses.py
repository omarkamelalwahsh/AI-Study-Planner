"""
Course data ingestion script.
Reads courses.csv, generates embeddings, stores in DB and FAISS index.
"""
import asyncio
import csv
import os
import sys
import pickle
import uuid
import numpy as np
import faiss
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sentence_transformers import SentenceTransformer
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models import Course, CourseEmbedding

# Convert database URL for async
database_url = settings.database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def load_csv_data(csv_path: str):
    """Load course data from CSV with BOM handling."""
    courses = []
    
    # Use utf-8-sig to automatically handle BOM
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            # Clean field names (strip BOM, spaces, etc.)
            row = {k.strip().lstrip('\ufeff'): v for k, v in row.items()}
            
            # Safely get values with fallback
            course_id = row.get('course_id', '').strip()
            if not course_id:
                course_id = str(uuid.uuid4())
                print(f"⚠️  Row {i+1}: No ID, generated {course_id}")
            
            title = row.get('title', '').strip()
            if not title:
                print(f"⚠️  Row {i+1}: No title, skipping")
                continue
            
            # Parse duration safely
            try:
                duration = float(row.get('duration_hours', 0) or 0)
            except (ValueError, TypeError):
                duration = 0.0
            
            courses.append({
                'course_id': course_id,
                'title': title,
                'category': row.get('category', '').strip() or None,
                'level': row.get('level', '').strip() or None,
                'duration_hours': duration,
                'skills': row.get('skills', '').strip() or None,
                'description': row.get('description', '').strip() or None,
                'instructor': row.get('instructor', '').strip() or None,
                'cover': row.get('cover', '').strip() or None,
            })
    
    print(f"✓ Loaded {len(courses)} courses from CSV")
    return courses


async def insert_courses(courses: list):
    """Insert courses into database."""
    async with async_session_maker() as session:
        try:
            # Clear existing courses
            await session.execute(text("TRUNCATE TABLE courses CASCADE"))
            
            # Insert new courses
            for course_data in courses:
                course = Course(**course_data)
                session.add(course)
            
            await session.commit()
            print(f"✓ Inserted {len(courses)} courses into database")
            
        except Exception as e:
            await session.rollback()
            print(f"✗ Database insertion failed: {e}")
            raise


def generate_embeddings(courses: list, model_name: str):
    """Generate embeddings using SentenceTransformer."""
    print(f"Loading embedding model: {model_name}...")
    model = SentenceTransformer(model_name)
    
    # Build text chunks
    chunks = []
    course_ids = []
    
    for course in courses:
        # Chunk = title + description + skills + category
        chunk_text = f"{course['title']}. {course['description'] or ''}. Skills: {course['skills'] or ''}. Category: {course['category'] or 'General'}"
        chunks.append(chunk_text[:500])  # Truncate for safety
        course_ids.append(course['course_id'])
    
    # Generate embeddings (batch processing)
    print(f"Generating embeddings for {len(chunks)} courses...")
    embeddings = model.encode(chunks, show_progress_bar=True, batch_size=32)
    
    print(f"✓ Generated {len(embeddings)} embeddings")
    return embeddings, course_ids, chunks


def build_faiss_index(embeddings: np.ndarray, course_ids: list, output_path: str):
    """Build FAISS index and save mapping."""
    dimension = embeddings.shape[1]
    
    # Create FAISS index (L2 distance)
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype('float32'))
    
    print(f"✓ Built FAISS index with {index.ntotal} vectors (dim={dimension})")
    
    # Save index
    os.makedirs(output_path, exist_ok=True)
    faiss_file = os.path.join(output_path, "courses.faiss")
    faiss.write_index(index, faiss_file)
    print(f"✓ Saved FAISS index to {faiss_file}")
    
    # Save ID mapping
    mapping = {i: str(course_ids[i]) for i in range(len(course_ids))}
    mapping_file = os.path.join(output_path, "id_mapping.pkl")
    with open(mapping_file, 'wb') as f:
        pickle.dump(mapping, f)
    print(f"✓ Saved ID mapping to {mapping_file}")


async def store_embeddings_metadata(course_ids: list, chunks: list, model_name: str):
    """Store embedding metadata in database."""
    async with async_session_maker() as session:
        try:
            # Clear existing embeddings
            await session.execute(text("TRUNCATE TABLE course_embeddings"))
            
            # Insert embeddings metadata
            for course_id, chunk_text in zip(course_ids, chunks):
                embedding_meta = CourseEmbedding(
                    course_id=course_id,
                    embedding_model=model_name,
                    chunk_text=chunk_text,
                    embedding_meta={"source": "csv", "version": "1.0"}
                )
                session.add(embedding_meta)
            
            await session.commit()
            print(f"✓ Stored {len(course_ids)} embedding metadata records")
            
        except Exception as e:
            await session.rollback()
            print(f"✗ Embedding metadata insertion failed: {e}")
            raise


async def main():
    """Main ingestion pipeline."""
    print("=" * 60)
    print("Career Copilot RAG - Course Data Ingestion")
    print("=" * 60)
    
    # Paths
    csv_path = "data/courses.csv"
    faiss_output = settings.faiss_index_path
    
    # Step 1: Load CSV
    print("\n[1/5] Loading CSV data...")
    courses = await load_csv_data(csv_path)
    
    # Step 2: Insert into database
    print("\n[2/5] Inserting courses into database...")
    await insert_courses(courses)
    
    # Step 3: Generate embeddings
    print("\n[3/5] Generating embeddings...")
    model_name = settings.embed_model_name
    embeddings, course_ids, chunks = generate_embeddings(courses, model_name)
    
    # Step 4: Build FAISS index
    print("\n[4/5] Building FAISS index...")
    build_faiss_index(embeddings, course_ids, faiss_output)
    
    # Step 5: Store metadata
    print("\n[5/5] Storing embedding metadata...")
    await store_embeddings_metadata(course_ids, chunks, model_name)
    
    print("\n" + "=" * 60)
    print("✓ Data ingestion complete!")
    print("=" * 60)
    print(f"  • Courses: {len(courses)}")
    print(f"  • Embeddings: {len(embeddings)}")
    print(f"  • FAISS index: {faiss_output}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

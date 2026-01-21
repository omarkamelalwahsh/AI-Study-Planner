import sys
import os
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.db import SessionLocal, engine
from app.models import Course

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

def load_data():
    csv_path = os.path.join(DATA_DIR, 'courses.csv')
    parquet_path = os.path.join(DATA_DIR, 'courses.parquet')

    if os.path.exists(csv_path):
        print(f"Loading CSV from {csv_path}")
        return pd.read_csv(csv_path)
    elif os.path.exists(parquet_path):
        print(f"Loading Parquet from {parquet_path}")
        return pd.read_parquet(parquet_path)
    else:
        print(f"No data file found in {DATA_DIR}. Expected courses.csv or courses.parquet")
        sys.exit(1)

def map_columns(df: pd.DataFrame):
    """Normalize column names to match DB schema"""
    cols = df.columns.str.lower().str.strip()
    df.columns = cols
    
    mapping = {
        'name': 'title',
        'course_title': 'title',
        'desc': 'description',
        'overview': 'description',
        'link': 'url',
        'course_url': 'url'
    }
    
    df.rename(columns=mapping, inplace=True)
    
    # Ensure required columns or defaults
    expected_cols = ['title', 'description', 'category', 'level', 'duration_hours', 'skills', 'instructor', 'cover', 'url']
    
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None 
            
    # Handle duration if it needs parsing (simple robust check, assumes mostly float or cleans it)
    # This is a basic cleaning, assuming data is relatively clean or will be cast to None if error
    if 'duration_hours' in df.columns:
         df['duration_hours'] = pd.to_numeric(df['duration_hours'], errors='coerce')
    
    return df

def ingest():
    df = load_data()
    print(f"Loaded {len(df)} rows.")
    print("Columns:", df.columns.tolist())
    
    df = map_columns(df)
    
    # row_idx handling
    if 'row_idx' not in df.columns:
        df['row_idx'] = range(len(df))
    else:
        # Ensure row_idx is unique and integer
        df['row_idx'] = df['row_idx'].astype(int)
        
    # Replace NaN with None for SQL compat
    df = df.replace({np.nan: None})
    
    records = df.to_dict(orient='records')
    
    db: Session = SessionLocal()
    try:
        total_upserted = 0
        for row in records:
            stmt = insert(Course).values(
                row_idx=row['row_idx'],
                title=row.get('title') or "Untitled",
                description=row.get('description'),
                category=row.get('category'),
                level=row.get('level'),
                duration_hours=row.get('duration_hours'),
                skills=row.get('skills'),
                instructor=row.get('instructor'),
                cover=row.get('cover'),
                url=row.get('url')
            )
            
            # UPSERT: Update all fields on conflict
            do_update_stmt = stmt.on_conflict_do_update(
                index_elements=['row_idx'],
                set_={
                    'title': stmt.excluded.title,
                    'description': stmt.excluded.description,
                    'category': stmt.excluded.category,
                    'level': stmt.excluded.level,
                    'duration_hours': stmt.excluded.duration_hours,
                    'skills': stmt.excluded.skills,
                    'instructor': stmt.excluded.instructor,
                    'cover': stmt.excluded.cover,
                    'url': stmt.excluded.url
                }
            )
            
            db.execute(do_update_stmt)
            total_upserted += 1
            
        db.commit()
        print(f"Successfully processed {total_upserted} rows.")
        
        # Check URL stats
        url_count = db.query(Course).filter(Course.url.isnot(None)).count()
        print(f"Rows with non-null URL: {url_count}")
        
    except Exception as e:
        db.rollback()
        print(f"Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    ingest()

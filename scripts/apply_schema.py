"""
Simple script to apply database schema using Python.
Alternative to: psql -d career_copilot -f database/schema.sql
"""
import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def apply_schema():
    """Apply database schema from schema.sql file."""
    print("=" * 60)
    print("Applying Database Schema")
    print("=" * 60)
    
    # Read schema file
    print("\n[1/2] Reading schema.sql...")
    with open('database/schema.sql', 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # Get DATABASE_URL from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL not found in .env file")
    
    # Convert async URL to sync for psycopg2
    db_url = db_url.replace(
        "postgresql+asyncpg://",
        "postgresql://"
    ).replace(
        "postgresql+psycopg2://",
        "postgresql://"
    )
    
    print(f"[2/2] Applying schema to database...")
    print(f"Database: {db_url.split('@')[-1] if '@' in db_url else 'career_copilot'}")
    
    try:
        # Connect to database
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Execute schema
        cursor.execute(schema_sql)
        
        # Verify tables created
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        print("\n✓ Schema applied successfully!")
        print(f"\nTables created ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")
        
        print("\n" + "=" * 60)
        print("✓ Database ready!")
        print("=" * 60)
        
    except psycopg2.Error as e:
        print(f"\n✗ Error applying schema: {e}")
        print("\nMake sure:")
        print("  1. PostgreSQL is running")
        print("  2. DATABASE_URL in .env is correct")
        print("  3. Database 'career_copilot' exists")
        raise

if __name__ == "__main__":
    apply_schema()

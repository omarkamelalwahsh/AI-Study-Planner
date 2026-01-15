from sqlalchemy import text
from app.db import engine
import os

def apply_migration():
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "v2_embeddings_table.sql")
    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()
    
    with engine.connect() as conn:
        print("Applying migration...")
        conn.execute(text(sql))
        conn.commit()
        print("Migration applied successfully.")

if __name__ == "__main__":
    apply_migration()


import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import SessionLocal
from app.search.embedding import get_embedding
from app.core.config import settings

logger = logging.getLogger(__name__)

class DBRetrievalService:
    _instance = None
    _courses_df = None
    _embeddings_matrix = None
    _course_ids = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBRetrievalService, cls).__new__(cls)
            cls._instance.reload_data()
        return cls._instance

    def reload_data(self):
        """
        Loads courses and embeddings from Postgres into memory.
        """
        logger.info("Reloading retrieval data from DB...")
        db: Session = SessionLocal()
        try:
            # Fetch embeddings
            # We assume model_name matches settings.EMBED_MODEL_NAME or we just take the first one?
            # Ideally we filter by the current active model.
            target_model = settings.EMBED_MODEL_NAME or "intfloat/multilingual-e5-small"
            
            # Fetch embeddings
            # (course_id, embedding)
            emb_query = text("""
                SELECT course_id, embedding 
                FROM course_embeddings 
                WHERE model_name = :mn
            """)
            emb_rows = db.execute(emb_query, {"mn": target_model}).fetchall()
            
            if not emb_rows:
                logger.warning(f"No embeddings found for model {target_model}")
                self._embeddings_matrix = np.array([])
                self._course_ids = []
                # Fetch courses anyway for category listing?
            else:
                self._course_ids = [str(r[0]) for r in emb_rows]
                # Convert list of floats to numpy array
                self._embeddings_matrix = np.array([r[1] for r in emb_rows], dtype="float32")
                # Normalize for cosine similarity
                # (norm=L2). E5 embeddings might already be normalized, but good to be safe.
                from sklearn.preprocessing import normalize
                self._embeddings_matrix = normalize(self._embeddings_matrix, norm='l2', axis=1)

            # Fetch course metadata for all courses
            # We fetch as dataframe for easy filtering/formatting
            query = text("SELECT * FROM courses")
            # Pandas read_sql requires a connection, not session
            self._courses_df = pd.read_sql(query, db.bind)
            
            # Index by id for fast lookup
            if not self._courses_df.empty:
                self._courses_df['id'] = self._courses_df['id'].astype(str)
                self._courses_df = self._courses_df.set_index('id')
            
            logger.info(f"Loaded {len(self._courses_df)} courses and {len(self._course_ids)} embeddings.")

        except Exception as e:
            logger.error(f"Failed to load retrieval data: {e}")
            raise e
        finally:
            db.close()

    def search(self, query: str, top_k: int = 5, score_threshold: float = 0.5) -> List[Dict]:
        """
        Embeds query and searches in-memory embeddings.
        """
        if not query:
            return []
        
        if self._embeddings_matrix is None or len(self._embeddings_matrix) == 0:
            logger.warning("Search called but no embeddings loaded.")
            return []

        # 1. Embed Query
        query_vec = get_embedding(query, embedding_type="query")
        if query_vec is None:
            return []
        
        query_vec = np.array([query_vec], dtype="float32")
        # Normalize
        from sklearn.preprocessing import normalize
        query_vec = normalize(query_vec, norm='l2', axis=1)

        # 2. Cosine Similarity (Dot product of normalized vectors)
        # matrix: [N, D], query: [1, D] -> [N, 1]
        scores = np.dot(self._embeddings_matrix, query_vec.T).flatten()

        # 3. Top K
        # Sort desc
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = scores[idx]
            if score < score_threshold:
                continue
                
            c_id = self._course_ids[idx]
            
            # Lookup metadata
            if c_id in self._courses_df.index:
                row = self._courses_df.loc[c_id].to_dict()
                row["score"] = float(score)
                # Map 'id' back from index
                row["id"] = c_id
                results.append(row)
        
        return results

    def get_best_matches(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Retrieves the top `limit` relevant courses for the LLM context.
        Returns a list of dicts strictly formatted for the 'catalog' context field.
        """
        # Reuse existing search logic logic for ranking
        raw_results = self.search(query, top_k=limit, score_threshold=0.45)
        
        catalog = []
        for r in raw_results:
            # Parse 'skills' if it's a string, or keep as is if list
            # The DB/CSV might store it as string representation of list or JSON
            # We'll try to ensure it's a list.
            skills_val = r.get('skills', [])
            if isinstance(skills_val, str):
                # Simple heuristic to convert string list to list if needed
                # e.g. "['Python', 'Django']" -> complex, for now treat as single string or split by comma
                if "," in skills_val:
                    skills_val = [s.strip() for s in skills_val.split(",")]
                else:
                    skills_val = [skills_val]
            elif skills_val is None:
                skills_val = []
                
            # Normalize level to English for LLM consistency
            raw_level = r.get("level", "Beginner")
            normalized_level = "Beginner"
            level_map = {
                "مبتدئ": "Beginner", "مبتدأ": "Beginner", "ابتدائي": "Beginner",
                "متوسط": "Intermediate",
                "متقدم": "Advanced", "احترافي": "Advanced"
            }
            # Also check if it's already English
            if isinstance(raw_level, str):
                if raw_level in ["Beginner", "Intermediate", "Advanced"]:
                    normalized_level = raw_level
                else:
                    normalized_level = level_map.get(raw_level, "Beginner")

            catalog.append({
                "course_id": str(r.get("id")),
                "title": self.sanitize_text(r.get("title")),
                "category": r.get("category", "General"),
                "level": normalized_level,
                "duration_hours": r.get("duration_hours", 0) or 0,
                "instructor": self.sanitize_text(r.get("instructor", "Unknown")),
                "skills": skills_val,
                "description": r.get("description", "")[:300] # Limit description length for context window
            })
            
        return catalog

    def get_tracks(self, category_query: str, limit: int = 4) -> List[str]:
        """
        Retrieves top distinct 'tracks' (usually sub-categories or popular course titles)
        for a broad category to help the user narrow down their choice.
        """
        # Search for the category
        raw_results = self.search(category_query, top_k=20, score_threshold=0.3)
        
        # Extract unique categories/levels/topics as tracks
        tracks = set()
        for r in raw_results:
            title = r.get("title", "")
            # Simple heuristic: use the part before ":" or "-" in title if exists, or just title
            # and maybe the category itself if it's more specific?
            # For now, let's take the top distinct titles as representative tracks
            # but clean them up to be short
            clean_title = title.split(":")[0].split("-")[0].strip()
            if clean_title:
                tracks.add(clean_title)
            
            if len(tracks) >= limit:
                break
        
        # Fallback if no specific titles found
        if not tracks:
            # Maybe return the category aliases
            tracks = {"Basics", "Advanced Topics", "Practical Projects", "Career Paths"}
            
        return list(tracks)[:limit]

    def sanitize_text(self, text: str) -> str:
        """
        Removes CJK characters and other non-standard symbols to fix encoding visual issues.
        Keeps Arabic, English, numbers, and standard punctuation.
        Returns a fallback if string becomes empty or too short.
        """
        if not text:
            return "N/A"
        
        # Regex to keep: 
        # \w = [a-zA-Z0-9_] (plus unicode chars depending on flag, but we'll be explicit)
        # We want to keep Latin, Arabic (\u0600-\u06FF), Numbers, common punctuation.
        import re
        # This regex matches allowed characters. We join them.
        # Allowed: Latin(a-z), Arabic(0600-06FF), Digits, Whitespace, Punctuation(.,-&|:()')
        
        # Alternatively, identifying "Bad" characters (CJK) and removing them.
        # CJK ranges: \u4e00-\u9fff, \u3000-\u303f, etc.
        # Simple heuristic: If it contains CJK, replace/clean.
        
        # Let's try to remove known bad patterns or just filter allow-list.
        # Allow-list is safer.
        cleaned = re.sub(r'[^\w\s\u0600-\u06FF\.,\-\(\)\&\'"!:|]', '', text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        if not cleaned or len(cleaned) < 2:
            return "Zedny Production"  # Fallback as requested
            
        return cleaned

    def format_courses_for_prompt(self, courses: List[Dict]) -> str:
        """
        Formatting logic for the prompt.
        """
        if not courses:
            return "No specific courses found for this query."
        
        formatted = "Available Courses:\n"
        for i, c in enumerate(courses, 1):
            title = self.sanitize_text(c.get('title', 'Untitled'))
            level = c.get('level', 'N/A')
            instructor = self.sanitize_text(c.get('instructor', 'N/A'))
            skills = c.get('skills', 'N/A')
            desc = c.get('description', '') or 'N/A'
            duration = c.get('duration', 'N/A')
            url = c.get('url', 'N/A')
            
            formatted += f"{i}. {title}\n"
            formatted += f"   - Level: {level}\n"
            formatted += f"   - Instructor: {instructor}\n"
            formatted += f"   - Duration: {duration}\n"
            formatted += f"   - Skills: {skills}\n"
            formatted += f"   - URL: {url}\n"
            formatted += f"   - Description: {desc[:200]}...\n\n"
        return formatted

    def get_top_categories(self, limit: int = 6) -> List[str]:
        if self._courses_df is None or self._courses_df.empty:
            return []
        if 'category' not in self._courses_df.columns:
            return []
        
        return self._courses_df['category'].dropna().value_counts().head(limit).index.tolist()

    def get_top_categories_db(self, db: Session, limit: int = 20) -> List[str]:
        q = text("""
            SELECT category, COUNT(*) AS n
            FROM courses
            WHERE category IS NOT NULL AND TRIM(category) <> ''
            GROUP BY category
            ORDER BY n DESC
            LIMIT :limit;
        """)
        rows = db.execute(q, {"limit": limit}).fetchall()
        return [r[0] for r in rows if r[0]]

    def get_category_examples(self, db: Session, category: str, k: int = 3) -> List[Dict[str, Any]]:
        q = text("""
            SELECT id, title, level, duration_hours, skills
            FROM courses
            WHERE category = :category
            ORDER BY row_idx ASC
            LIMIT :k;
        """)
        rows = db.execute(q, {"category": category, "k": k}).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": str(r[0]),
                "title": r[1],
                "level": r[2],
                "duration_hours": r[3],
                "skills": r[4],
            })
        return out

    def get_categories_with_examples(self, db: Session, limit_categories: int = 10, k_examples: int = 3) -> List[Dict[str, Any]]:
        cats = self.get_top_categories_db(db, limit=limit_categories)
        data = []
        for c in cats:
            data.append({
                "category": c,
                "examples": self.get_category_examples(db, c, k=k_examples)
            })
        return data

    def get_fallback_courses(self, db: Session, k: int = 5) -> List[Dict[str, Any]]:
        q = text("SELECT id, title, level, duration_hours, skills FROM courses ORDER BY row_idx ASC LIMIT :k")
        rows = db.execute(q, {"k": k}).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": str(r[0]),
                "title": r[1],
                "level": r[2],
                "duration_hours": r[3],
                "skills": r[4],
            })
        return out

"""
Category Service - Single Source of Truth for Course Categories.
Loaded directly from courses.csv.
"""
import pandas as pd
import logging
from typing import List
from config import COURSES_CSV

logger = logging.getLogger(__name__)

class CategoryService:
    def __init__(self):
        self._categories = []
        self._initialized = False

    def load(self):
        """Loads categories from courses.csv."""
        if not COURSES_CSV.exists():
            logger.error(f"CategoryService: courses.csv not found at {COURSES_CSV}")
            return
        
        try:
            df = pd.read_csv(COURSES_CSV)
            if 'category' in df.columns:
                # Get unique categories, drop NaNs, strip whitespace, sort
                cats = df['category'].dropna().astype(str).str.strip().unique().tolist()
                self._categories = sorted([c for c in cats if c])
                logger.info(f"CategoryService: Loaded {len(self._categories)} valid categories from CSV.")
            else:
                logger.error("CategoryService: 'category' column missing in courses.csv")
            self._initialized = True
        except Exception as e:
            logger.error(f"CategoryService: Failed to load from CSV: {e}")
            self._categories = []

    def get_all(self) -> List[str]:
        if not self._initialized:
            self.load()
        return self._categories

    def is_valid(self, category: str) -> bool:
        return category in self.get_all()

# Global singleton
category_service = CategoryService()

"""
Career Copilot RAG Backend - Data Loader
Loads and caches courses, skills catalog, and indexes.
"""
import json
import pandas as pd
from typing import Dict, List, Optional
from pathlib import Path
import logging

from config import COURSES_CSV, SKILLS_CATALOG_CSV, SKILL_TO_COURSES_INDEX

logger = logging.getLogger(__name__)


class DataLoader:
    """Singleton data loader that caches all data on first load."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not DataLoader._initialized:
            self.courses_df: Optional[pd.DataFrame] = None
            self.skills_df: Optional[pd.DataFrame] = None
            self.skill_to_courses: Dict[str, List[dict]] = {}
            self.skill_aliases: Dict[str, str] = {}  # alias -> normalized skill
            self.all_skills_set: set = set()
            DataLoader._initialized = True
    
    def load_all(self) -> bool:
        """Load all data files. Returns True if successful."""
        try:
            self._load_courses()
            self._load_skills_catalog()
            self._load_skill_to_courses_index()
            logger.info("All data loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            return False
    
    def _load_courses(self):
        """Load courses.csv into DataFrame."""
        if not COURSES_CSV.exists():
            raise FileNotFoundError(f"Courses file not found: {COURSES_CSV}")
        
        self.courses_df = pd.read_csv(COURSES_CSV)
        logger.info(f"Loaded {len(self.courses_df)} courses")
    
    def _load_skills_catalog(self):
        """Load skills catalog and build alias mapping."""
        if not SKILLS_CATALOG_CSV.exists():
            raise FileNotFoundError(f"Skills catalog not found: {SKILLS_CATALOG_CSV}")
        
        self.skills_df = pd.read_csv(SKILLS_CATALOG_CSV)
        
        # Build skill set and alias mapping
        for _, row in self.skills_df.iterrows():
            skill_norm = str(row['skill_norm']).lower().strip()
            self.all_skills_set.add(skill_norm)
            
            # Parse aliases (comma-separated)
            aliases_str = str(row.get('aliases', ''))
            if aliases_str and aliases_str != 'nan':
                for alias in aliases_str.split(','):
                    alias = alias.strip().lower()
                    if alias:
                        self.skill_aliases[alias] = skill_norm
        
        logger.info(f"Loaded {len(self.skills_df)} skills with {len(self.skill_aliases)} aliases")
    
    def _load_skill_to_courses_index(self):
        """Load pre-built skill to courses mapping."""
        if not SKILL_TO_COURSES_INDEX.exists():
            raise FileNotFoundError(f"Skill index not found: {SKILL_TO_COURSES_INDEX}")
        
        with open(SKILL_TO_COURSES_INDEX, 'r', encoding='utf-8') as f:
            self.skill_to_courses = json.load(f)
        
        logger.info(f"Loaded skill->courses index with {len(self.skill_to_courses)} entries")
    
    def get_course_by_id(self, course_id: str) -> Optional[dict]:
        """Get full course details by ID."""
        if self.courses_df is None:
            return None
        
        matches = self.courses_df[self.courses_df['course_id'] == course_id]
        if matches.empty:
            return None
        
        return matches.iloc[0].to_dict()
    
    def search_courses_by_title(self, query: str) -> List[dict]:
        """Search courses by title (case-insensitive partial match)."""
        if self.courses_df is None:
            return []
        
        query_lower = query.lower()
        matches = self.courses_df[
            self.courses_df['title'].str.lower().str.contains(query_lower, na=False)
        ]
        return matches.to_dict('records')
    
    def get_courses_for_skill(self, skill: str) -> List[dict]:
        """Get courses associated with a skill."""
        skill_lower = skill.lower().strip()
        
        # Check direct match
        if skill_lower in self.skill_to_courses:
            return self.skill_to_courses[skill_lower]
        
        # Check aliases
        if skill_lower in self.skill_aliases:
            normalized = self.skill_aliases[skill_lower]
            return self.skill_to_courses.get(normalized, [])
        
        return []
    
    def validate_skill(self, skill: str) -> Optional[str]:
        """
        Validate if skill exists in catalog.
        Returns normalized skill name if valid, None otherwise.
        """
        skill_lower = skill.lower().strip()
        
        # Direct match
        if skill_lower in self.all_skills_set:
            return skill_lower
        
        # Alias match
        if skill_lower in self.skill_aliases:
            return self.skill_aliases[skill_lower]
        
        return None
    
    def get_skill_info(self, skill: str) -> Optional[dict]:
        """Get full skill information from catalog."""
        if self.skills_df is None:
            return None
        
        skill_lower = skill.lower().strip()
        
        # Handle alias
        if skill_lower in self.skill_aliases:
            skill_lower = self.skill_aliases[skill_lower]
        
        matches = self.skills_df[self.skills_df['skill_norm'].str.lower() == skill_lower]
        if matches.empty:
            return None
        
        return matches.iloc[0].to_dict()
    
    def get_all_categories(self) -> List[str]:
        """Get all unique course categories."""
        if self.courses_df is None:
            return []
        return self.courses_df['category'].dropna().unique().tolist()
    
    def get_all_domains(self) -> List[str]:
        """Get all unique skill domains."""
        if self.skills_df is None:
            return []
        return self.skills_df['domain'].dropna().unique().tolist()


# Global instance
data_loader = DataLoader()

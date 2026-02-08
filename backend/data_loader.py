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
from catalog import category_service

logger = logging.getLogger(__name__)


class DataLoader:
    """Singleton data loader that caches all data on first load."""
    
    _instance = None
    _initialized = False
    
    def get_valid_categories(self) -> List[str]:
        """
        Returns strict list of categories that actually exist in courses.csv.
        Integrated with CategoryService.
        """
        return category_service.get_all()

    def get_categories_for_role(self, role: str) -> List[str]:
        """
        Returns relevant categories for a role based on keyword matching against ACTUAL categories.
        Dynamic, no hardcoding.
        """
        valid_cats = self.get_valid_categories()
        if not role: 
            return valid_cats[:5] # Default fallback

        role_lower = role.lower().strip()
        
        # 1. Resolve Arabic Aliases
        if role_lower in self.ROLE_ARABIC_ALIASES:
             role_lower = self.ROLE_ARABIC_ALIASES[role_lower].lower()

        # 2. Dynamic Keyword Matching
        # We try to match role keywords with category names
        matched = []
        
        # Keywords to check against categories
        keywords = role_lower.split()
        
        # Special mappings for broad roles to ensure coverage if keywords miss
        # BUT only mapping to keywords, not hardcoded categories
        meta_mappings = {
            "backend": ["programming", "web", "database", "api"],
            "frontend": ["web", "design", "javascript"],
            "full stack": ["programming", "web", "database"],
            "data": ["data", "analysis", "science", "sql", "intelligence"],
            "manager": ["management", "leadership", "business", "project"],
            "sales": ["sales", "marketing", "business", "negotiation"],
            "hr": ["resources", "human", "management"],
            "marketing": ["marketing", "social", "content", "digital"],
        }
        
        search_terms = keywords
        for k, v in meta_mappings.items():
            if k in role_lower:
                search_terms.extend(v)
        
        search_terms = list(set(search_terms)) # dedup

        for cat in valid_cats:
            cat_lower = cat.lower()
            # If any search term is part of the category name
            if any(term in cat_lower for term in search_terms):
                matched.append(cat)
        
        # If no strict matches, return broad categories (failsafe)
        if not matched:
            # Return top 5 generic categories if available, else all
            return valid_cats[:5]

        return sorted(list(set(matched)))

    # Arabic Role Aliases (Mapped to normalized keys)
    ROLE_ARABIC_ALIASES = {
        "مدير مبيعات": "Sales Manager",
        "مدير مبرمجين": "Engineering Manager",
        "مدير hr": "HR Manager",
        "مدير موارد بشرية": "HR Manager",
        "مدير ai": "AI Manager",
        "مدير تسويق": "Marketing Manager",
        "مدير مالي": "Finance Manager",
        "مدير مشاريع": "Project Management",
        "مبرمج": "Backend Development",
        "فرونت": "Frontend Development",
        "باك": "Backend Development",
        "مصمم": "Web Design",
        # V18 FIX 2
        "داتا انجينير": "Data Engineer",
        "مهندس بيانات": "Data Engineer",
        "داتا انالست": "Data Analyst",
        "محلل بيانات": "Data Analyst",
    }

    # Centralized Role Policy (Required skills for key tracks)
    ROLE_POLICY = {
        "Data Analyst": ["SQL", "Python", "Data Visualization", "Statistics", "Excel"],
        "Backend Developer": ["Python", "SQL", "API", "Databases", "Linux"],
        "Frontend Developer": ["HTML", "CSS", "JavaScript", "React", "Web Design"],
        "Full Stack Developer": ["HTML", "CSS", "JavaScript", "SQL", "Python", "API"],
        "Sales Manager": ["Sales", "Negotiation", "Communication", "CRM", "Leadership"],
        "Marketing Manager": ["Marketing", "Digital Marketing", "Social Media", "SEO", "Analytics"],
        "HR Manager": ["Human Resources", "Recruitment", "Training", "Team Management"],
        "Project Manager": ["Project Management", "Agile", "Scrum", "Leadership", "Communication"],
    }

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
        
        # SECURITY FIX: Remove logic-exposed JWT tokens from URLs
        if 'cover' in self.courses_df.columns:
            # Remove everything starting from '?token=' to the end of the string
            self.courses_df['cover'] = self.courses_df['cover'].astype(str).str.replace(r'\?token=.*', '', regex=True)
            
        logger.info(f"Loaded {len(self.courses_df)} courses")
        # Sync CategoryService
        category_service.load()
    
    @staticmethod
    def normalize_skill(skill: str) -> str:
        """Robust skill normalization: lowercase, strip, remove special chars"""
        import re
        s = str(skill).lower().strip()
        s = re.sub(r"[_\-]+", " ", s) # Replace _ and - with space
        s = re.sub(r"\s+", " ", s)    # Collapse multiple spaces
        return s

    @staticmethod
    def normalize_category(category: str) -> str:
        """Normalize category name for comparison."""
        import re
        s = str(category).lower().strip()
        s = re.sub(r"[&_,.\s\-]+", "", s) # Remove all separators
        return s

    def get_normalized_categories(self) -> Dict[str, str]:
        """
        Returns a mapping of normalized category names to their display names.
        """
        all_cats = self.get_all_categories()
        return {self.normalize_category(cat): cat for cat in all_cats}

    def _load_skills_catalog(self):
        """Load skills catalog and build alias mapping."""
        if not SKILLS_CATALOG_CSV.exists():
            raise FileNotFoundError(f"Skills catalog not found: {SKILLS_CATALOG_CSV}")
        
        self.skills_df = pd.read_csv(SKILLS_CATALOG_CSV)
        
        # Build skill set and alias mapping
        for _, row in self.skills_df.iterrows():
            skill_norm = self.normalize_skill(row['skill_norm'])
            self.all_skills_set.add(skill_norm)
            
            # Parse aliases (comma-separated)
            aliases_str = str(row.get('aliases', ''))
            if aliases_str and aliases_str != 'nan':
                for alias in aliases_str.split(','):
                    alias_norm = self.normalize_skill(alias)
                    if alias_norm:
                        self.skill_aliases[alias_norm] = skill_norm
        
        # Inject critical manual aliases (Runtime fix for "3D Printing" discrepancy)
        manual_aliases = {
            # Database aliases
            "database": "databases",
            "data base": "databases",
            "قواعد بيانات": "databases",
            "قاعدة بيانات": "databases",
            "داتا بيز": "databases",
            "mysql": "databases",
            "sql": "databases",
            # 3D Printing aliases
            "3d printing": "3d modeling",
            "printing 3d": "3d modeling",
            "طباعة ثلاثية الابعاد": "3d modeling",
            "3d": "3d modeling",
            "3d max": "3d modeling",
            "ثري دي": "3d modeling",
            # Graphic Design aliases
            "جرافيك ديزاين": "graphic design",
            "تصميم جرافيك": "graphic design",
            "التصميم الجرافيكي": "graphic design",
            "graphic design": "graphic design",
            "graphic design": "graphic design",
            "design": "graphic design",
            # JavaScript aliases (V21 Fix)
            "java script": "javascript",
            "js": "javascript",
            "جافا سكريبت": "javascript",
            "جافاسكريبت": "javascript",
            "جافااسكريبت": "javascript"
        }
        for alias, norm in manual_aliases.items():
             self.skill_aliases[alias] = norm
             self.all_skills_set.add(norm) # Ensure target exists

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
        """Search courses by title OR category (case-insensitive partial match)."""
        if self.courses_df is None:
            return []
        
        query_lower = query.lower()
        # V6 Fix: Search in Title AND Category
        matches = self.courses_df[
            self.courses_df['title'].str.lower().str.contains(query_lower, na=False) |
            self.courses_df['category'].str.lower().str.contains(query_lower, na=False)
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
        """Get all unique course categories (sorted)."""
        if self.courses_df is None:
            return []
        cats = self.courses_df['category'].dropna().unique().tolist()
        return sorted(cats)
    
    def suggest_categories_for_topic(self, topic: str, top_n: int = 6) -> List[str]:
        """Suggest relevant categories for a broad topic based on keyword match."""
        if self.courses_df is None:
            return []
        q = str(topic).lower().strip()

        # curated keyword map (lightweight semantic bridge)
        keyword_to_cats = {
            "برمجة": ["Programming", "Web Development", "Mobile Development", "Technology Applications", "Networking", "Data Security"],
            "programming": ["Programming", "Web Development", "Mobile Development", "Technology Applications", "Networking", "Data Security"],
            "سايبر": ["Data Security", "Networking", "Technology Applications"],
            "cyber": ["Data Security", "Networking", "Technology Applications"],
            "ويب": ["Web Development", "Programming", "Graphics & Design"],
            "web": ["Web Development", "Programming", "Graphics & Design"],
            "موبايل": ["Mobile Development", "Programming"],
            "mobile": ["Mobile Development", "Programming"],
            "ديزاين": ["Graphics & Design", "Mobile Development", "Web Development"],
            "design": ["Graphics & Design", "Mobile Development", "Web Development"],
            "بيانات": ["Data Management", "Technology Applications", "Business Intelligence"],
            "data": ["Data Management", "Technology Applications", "Business Intelligence"],
            "ادارة": ["Management & Leadership", "Project Management", "Business Strategy"],
            "management": ["Management & Leadership", "Project Management", "Business Strategy"],
            "بزنس": ["Business Strategy", "Marketing", "Sales", "Management & Leadership"],
            "business": ["Business Strategy", "Marketing", "Sales", "Management & Leadership"],
            "تسويق": ["Marketing", "Sales", "Business Strategy"],
            "marketing": ["Marketing", "Sales", "Business Strategy"],
            "مبيعات": ["Sales", "Marketing", "Business Strategy"],
            "sales": ["Sales", "Marketing", "Business Strategy"],
            "سوفت سكيلز": ["Soft Skills", "Personal Development", "Communication Skills"],
            "soft skills": ["Soft Skills", "Personal Development", "Communication Skills"]
        }

        cats = set(self.get_all_categories())
        matched_cats = []
        
        # 1. Check keyword map
        for k, suggested in keyword_to_cats.items():
            if k in q:
                for c in suggested:
                    if c in cats and c not in matched_cats:
                        matched_cats.append(c)
        
        # 2. Check direct contains if we need more
        if len(matched_cats) < top_n:
            for c in sorted(list(cats)):
                c_low = c.lower()
                if (q in c_low or c_low in q) and c not in matched_cats:
                    matched_cats.append(c)
        
        return matched_cats[:top_n]

    def get_umbrella_categories(self, topic: str) -> List[str]:
        """Get categories for an umbrella topic (V16 - Broad Topic Disambiguation)."""
        topic_lower = topic.lower().strip()
        
        candidates = []
        
        # 1. Direct umbrella match
        if topic_lower in self.UMBRELLA_TOPICS:
            candidates = self.UMBRELLA_TOPICS[topic_lower]
        
        # 2. Fuzzy match against umbrella keys
        if not candidates:
            for key, cats in self.UMBRELLA_TOPICS.items():
                if key in topic_lower or topic_lower in key:
                    candidates = cats
                    break
        
        if not candidates:
            return []
            
        # 3. Filter against REAL categories (Data-Driven)
        real_cats = self.get_all_categories()
        real_cats_lower = {c.lower(): c for c in real_cats}
        
        valid_cats = []
        for c in candidates:
            # Try exact match (case-insensitive)
            if c.lower() in real_cats_lower:
                valid_cats.append(real_cats_lower[c.lower()])
                continue
                
            # Try fuzzy match (e.g. "Graphic Design" vs "Graphics & Design")
            # If the candidate is a substring of a real category or vice versa
            match = next((real for real in real_cats if c.lower() in real.lower() or real.lower() in c.lower()), None)
            if match and match not in valid_cats:
                valid_cats.append(match)
                
        return sorted(list(set(valid_cats)))

    def canonicalize_query(self, message: str) -> dict:
        """Deterministic mapping of keywords to domains (Stop Drift)."""
        msg = message.lower()
        
        # Backend Lock
        backend_kw = ["باك اند", "backend", "back-end", "server", "api", "rest", "graphql", 
                      "database", "sql", "postgres", "postgresql", "mysql", "داتابيز", "قاعدة بيانات"]
        # Database Lock (V27 Distinct from Backend)
        db_kw = ["database", "data base", "sql", "mysql", "postgres", "mongodb", "داتابيز", "قواعد بيانات", "قاعدة بيانات"]
        if any(kw in msg for kw in db_kw):
             return {
                "primary_domain": "Database Administration", # New domain key
                "focus_area": "Data Management", 
                "tool": "Database",
                "semantic_lock": True
             }
            
        # Frontend Lock
        frontend_kw = ["فرونت اند", "front-end", "frontend", "react", "vue", "angular", "css", "html", "javascript"]
        if any(kw in msg for kw in frontend_kw):
            return {
                "primary_domain": "Frontend Development",
                "focus_area": "Web Development",
                "tool": "Frontend",
                "semantic_lock": True
            }

        # Fullstack Lock
        fullstack_kw = ["فول ستاك", "fullstack", "full stack", "full-stack"]
        if any(kw in msg for kw in fullstack_kw):
            return {
                "primary_domain": "Backend Development",
                "secondary_domains": ["Frontend Development"],
                "focus_area": "Web Development",
                "semantic_lock": True
            }

        # UI/UX & Design Lock
        design_kw = ["ديزاين", "web design", "ux", "ui", "تصميم ويب", "يوزر انترفيس", "يو اكس"]
        if any(kw in msg for kw in design_kw):
            return {
                "primary_domain": "Web Design",
                "focus_area": "Web Development",
                "tool": "Design",
                "semantic_lock": True
            }
            
        # HR Lock
        hr_kw = ["hr", "human resources", "موارد بشرية", "شؤون موظفين"]
        if any(kw in msg for kw in hr_kw):
            return {
                "primary_domain": "HR",
                "semantic_lock": True
            }

        return {}

    def get_all_domains(self) -> List[str]:
        """Get all unique skill domains."""
        if self.skills_df is None:
            return []
        return self.skills_df['domain'].dropna().unique().tolist()
    
    def get_all_categories(self) -> List[str]:
        """Get all unique course categories from the data source (Single Source of Truth)."""
        if self.courses_df is None:
            return []
        
        cats = self.courses_df['category'].dropna().unique().tolist()
        return sorted(cats)


# Global instance
data_loader = DataLoader()

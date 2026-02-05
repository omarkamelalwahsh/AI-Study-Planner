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
    
    # Production-Grade Domain Whitelists (V14 - Expert Refinement)
    DOMAIN_CATEGORY_WHITELIST = {
        "Backend Development": ["Programming", "Web Development", "Data Security", "Networking", "Technology Applications", "Project Management"],
        "Frontend Development": ["Web Development", "Programming", "Graphic Design", "Technology Applications"],
        "HR": ["Human Resources", "Business Fundamentals", "Leadership & Management", "Soft Skills"],
        "Sales Management": ["Sales", "Leadership & Management", "Soft Skills", "Business Fundamentals", "Customer Service"],
        "Web Design": ["Web Development", "Graphics & Design", "Marketing", "Digital Media"],
        "Data Science": ["Data Management", "Programming", "Business Intelligence", "Business Strategy", "Technology Applications"],
        "Data Analysis": ["Data Management", "Business Intelligence", "Technology Applications", "Business Strategy"],
        "Sales": ["Sales", "Customer Service", "Marketing", "Business Strategy", "Business Fundamentals"],
        "Marketing": ["Marketing", "Sales", "Digital Media", "Business Strategy", "Communication Skills"],
        "Finance": ["Finance", "Accounting", "Business Strategy", "Business Fundamentals"],
        "Project Management": ["Project Management", "Management & Leadership", "Business Strategy", "Soft Skills"],
        "Soft Skills": ["Soft Skills", "Personal Development", "Communication Skills", "Career Development"],
        "Management": ["Leadership & Management", "Project Management", "Business Strategy", "Soft Skills", "Business Fundamentals"],
        "Mobile Development": ["Mobile Development", "Programming", "Technology Applications"]
    }

    # ROLE POLICY: Specific whitelists for common complex roles (Case-Insensitive resolved)
    ROLE_POLICY = {
        "Sales Manager": ["Sales", "Leadership & Management", "Soft Skills", "Business Fundamentals", "Customer Service", "Project Management"],
        "Engineering Manager": ["Leadership & Management", "Project Management", "Programming", "Web Development", "Soft Skills"],
        "HR Manager": ["Human Resources", "Leadership & Management", "Soft Skills", "Business Fundamentals"],
        "AI Manager": ["Leadership & Management", "Project Management", "Data Management", "Programming", "Business Strategy"],
        "Marketing Manager": ["Marketing", "Sales", "Leadership & Management", "Business Strategy", "Digital Media"],
        "Finance Manager": ["Finance", "Accounting", "Leadership & Management", "Business Strategy"],
        "Full Stack Developer": ["Programming", "Web Development", "Data Management", "Networking", "Technology Applications"],
        "Product Manager": ["Project Management", "Management & Leadership", "Marketing", "Business Strategy", "Soft Skills"],
        
        # V18 FIX 2: Accurate Data Roles
        "Data Engineer": ["Technology Applications", "Programming", "Data Management", "Networking"],
        "Data Analyst": ["Technology Applications", "Business Intelligence", "Data Management"],
        "Data Scientist": ["Technology Applications", "Programming", "Data Management", "Business Intelligence"],
    }

    # Skill Priority for specific roles (overrides LLM)
    ROLE_SKILL_PRIORITY = {
         "Data Engineer": ["SQL", "Database", "ETL", "Data Warehouse", "Python", "Data Pipeline"],
         "Data Analyst": ["SQL", "Excel", "Power BI", "Tableau", "Data Visualization"],
         "Data Scientist": ["Python", "Machine Learning", "Statistics", "SQL", "Data Analysis"],
    }
    
    # UMBRELLA TOPICS: Broad topics that map to multiple categories (V16)
    UMBRELLA_TOPICS = {
        "programming": ["Programming", "Web Development", "Mobile Development", "Data Security", "Networking", "Technology Applications"],
        "برمجة": ["Programming", "Web Development", "Mobile Development", "Data Security", "Networking", "Technology Applications"],
        "design": ["Graphic Design", "Digital Media", "Web Development", "Mobile Development"],
        "ديزاين": ["Graphic Design", "Digital Media", "Web Development", "Mobile Development"],
        "management": ["Leadership & Management", "Project Management", "Business Fundamentals", "Soft Skills"],
        "ادارة": ["Leadership & Management", "Project Management", "Business Fundamentals", "Soft Skills"],
        "hr": ["Human Resources", "Leadership & Management", "Soft Skills", "Business Fundamentals"],
        "موارد بشرية": ["Human Resources", "Leadership & Management", "Soft Skills", "Business Fundamentals"],
        "soft skills": ["Soft Skills", "Public Speaking", "Leadership & Management", "Personal Development"],
        "سوفت سكيلز": ["Soft Skills", "Public Speaking", "Leadership & Management", "Personal Development"],
        "marketing": ["Marketing Skills", "Sales", "Digital Media", "Business Fundamentals"],
        "تسويق": ["Marketing Skills", "Sales", "Digital Media", "Business Fundamentals"],
        "sales": ["Sales", "Customer Service", "Business Fundamentals", "Marketing Skills"],
        "مبيعات": ["Sales", "Customer Service", "Business Fundamentals", "Marketing Skills"],
        "data": ["Technology Applications", "Programming", "Business Fundamentals", "Data Security"],
        "بيانات": ["Technology Applications", "Programming", "Business Fundamentals", "Data Security"],
        "database": ["Data Security", "Programming", "Technology Applications", "Web Development"],
        "data base": ["Data Security", "Programming", "Technology Applications", "Web Development"],
        "داتابيز": ["Data Security", "Programming", "Technology Applications", "Web Development"],
        "قواعد بيانات": ["Data Security", "Programming", "Technology Applications", "Web Development"],
        "cyber": ["Data Security", "Networking", "Technology Applications"],
        "سايبر": ["Data Security", "Networking", "Technology Applications"],
        "security": ["Data Security", "Networking", "Technology Applications"],
    }
    
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
    
    def is_arabic(self, text: str) -> bool:
        """Determines if text has significant Arabic content (>15%)."""
        import re
        if not text: return False
        arabic_chars = re.findall(r'[\u0600-\u06FF]', text)
        return (len(arabic_chars) / len(text)) > 0.15
    
    @staticmethod
    def normalize_category(s: str) -> str:
        """Normalize category string for consistent comparison (V17 Single Source of Truth)."""
        import unicodedata
        import re
        if not s: return ""
        s = unicodedata.normalize('NFKC', str(s).lower().strip())
        s = s.replace('&', 'and')
        s = re.sub(r'\s+', ' ', s)
        return s
    
    def get_normalized_categories(self) -> Dict[str, str]:
        """Returns a dict mapping normalized category names to their original display names."""
        cats = self.get_all_categories()
        return {self.normalize_category(c): c for c in cats}
    
    def get_categories_for_role(self, role: str) -> List[str]:
        """Resolves a list of allowed categories for a given role/domain (Case-Insensitive)."""
        if not role: return []
        
        role_norm = role.strip().lower()
        
        # 1. Resolve Arabic Aliases
        if role_norm in self.ROLE_ARABIC_ALIASES:
             role_norm = self.ROLE_ARABIC_ALIASES[role_norm].lower()

        # 2. Check specific role policy
        for policy_key, whitelist in self.ROLE_POLICY.items():
            if policy_key.lower() == role_norm:
                return whitelist
            
        # 3. Check domain whitelist fallback
        for domain_key, whitelist in self.DOMAIN_CATEGORY_WHITELIST.items():
            if domain_key.lower() == role_norm:
                return whitelist
            
        return []
        
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
    
    @staticmethod
    def normalize_skill(skill: str) -> str:
        """Robust skill normalization: lowercase, strip, remove special chars"""
        import re
        s = str(skill).lower().strip()
        s = re.sub(r"[_\-]+", " ", s) # Replace _ and - with space
        s = re.sub(r"\s+", " ", s)    # Collapse multiple spaces
        return s

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

import logging
import json
import os
from typing import List, Dict, Any
from app.schemas_career import Citation

logger = logging.getLogger(__name__)

# Production data embedded for fallback/no-file-access
ROLES_KB_DATA = [
    {
        "role": "Software Engineer", 
        "sector": "Tech", 
        "required_skills": ["Python", "Algorithms", "System Design", "Databases", "Version Control"], 
        "roadmap": "1. Learn Python fundamentals\n2. Master Data Structures & Algorithms\n3. Learn SQL and Database Design\n4. Practice System Design concepts\n5. Build portfolio projects"
    },
    {
        "role": "Product Manager", 
        "sector": "Tech", 
        "required_skills": ["Agile", "User Research", "Roadmapping", "Prioritization", "Analytics"], 
        "roadmap": "1. Understand Product Lifecycle\n2. Master Agile & Scrum frameworks\n3. Learn User Research techniques\n4. Develop data-driven decision making\n5. Master stakeholder management"
    },
    {
        "role": "Manager", 
        "sector": "General", 
        "required_skills": ["Leadership", "Communication", "Conflict Resolution", "Strategic Planning", "Budgeting"], 
        "roadmap": "1. Develop core leadership principles\n2. Master professional communication\n3. Learn strategic planning and goal setting\n4. Master team management & conflict resolution\n5. Learn financial management and budgeting"
    },
    {
        "role": "Data Scientist", 
        "sector": "Tech", 
        "required_skills": ["Python", "Statistics", "Machine Learning", "Data Visualization", "Big Data"], 
        "roadmap": "1. Master Python & Mathematics\n2. Learn Statistical Analysis\n3. Master Data Wrangling & Visualization\n4. Learn Machine Learning Algorithms\n5. Master Deep Learning & Big Data tools"
    }
]

class RoleAdvisor:
    def __init__(self, role_kb_path: str = "app/services/career_copilot/roles.jsonl"):
        self.role_kb_path = role_kb_path
        self._roles_data = self._load_role_kb() or ROLES_KB_DATA

    def _load_role_kb(self) -> List[Dict[str, Any]]:
        roles = []
        if os.path.exists(self.role_kb_path):
            try:
                with open(self.role_kb_path, "r", encoding="utf-8") as f:
                    for line in f:
                        roles.append(json.loads(line))
            except Exception as e:
                logger.error(f"Failed to load Role KB: {e}")
        return roles

    def get_role_info(self, target_role: str, sector: str = None) -> Dict[str, Any]:
        """
        STEP 3 — ROADMAP GENERATION
        Generate a SKILLS/TOPICS roadmap. ordered Fundamentals -> Advanced.
        """
        best_match = None
        if target_role:
            for role_entry in self._roles_data:
                if target_role.lower() in role_entry["role"].lower():
                    best_match = role_entry
                    break
        
        if not best_match:
            # Vague or unknown role -> Provide generic roadmap
            return {
                "role": target_role or "Professional",
                "required_skills": ["Foundational Knowledge", "Soft Skills", "Technical Literacy", "Specialized Knowledge"],
                "roadmap": "1. Build foundational knowledge in your chosen field.\n2. Develop essential communication and problem-solving skills.\n3. Gain practical technical literacy.\n4. Specialize in advanced topics as you progress.",
                "citations": [Citation(source_type="role_kb", id="generic_template")]
            }
        
        return {
            "role": best_match["role"],
            "required_skills": best_match["required_skills"],
            "roadmap": best_match["roadmap"],
            "citations": [Citation(source_type="role_kb", id=best_match.get("role", "unknown"))]
        }

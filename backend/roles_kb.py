"""
Career Copilot RAG Backend - Roles Knowledge Base
Loads and provides access to role definitions and roadmaps.
"""
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass

from config import DATA_DIR

logger = logging.getLogger(__name__)

ROLES_FILE = DATA_DIR / "roles.jsonl"


@dataclass
class RoleDefinition:
    """A role definition with skills and roadmap."""
    role: str
    sector: str
    required_skills: List[str]
    roadmap: str


class RolesKnowledgeBase:
    """Knowledge base for role definitions and career roadmaps."""
    
    def __init__(self):
        self.roles: Dict[str, dict] = {}
        self._loaded = False
    
    def load(self) -> bool:
        """Load roles from JSONL file."""
        if not ROLES_FILE.exists():
            logger.warning(f"Roles file not found: {ROLES_FILE}")
            return False
        
        try:
            with open(ROLES_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        role_data = json.loads(line)
                        role_name = role_data.get('role', '').lower()
                        if role_name:
                            self.roles[role_name] = role_data
            
            self._loaded = True
            logger.info(f"Loaded {len(self.roles)} role definitions")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load roles: {e}")
            return False
    
    def get_role(self, role_name: str) -> Optional[dict]:
        """Get role definition by name."""
        if not self._loaded:
            self.load()
        
        role_lower = role_name.lower()
        
        # Direct match
        if role_lower in self.roles:
            return self.roles[role_lower]
        
        # Partial match
        for key, value in self.roles.items():
            if role_lower in key or key in role_lower:
                return value
        
        return None
    
    def get_skills_for_role(self, role_name: str) -> List[str]:
        """Get required skills for a role."""
        role = self.get_role(role_name)
        if role:
            return role.get('required_skills', [])
        return []
    
    def get_roadmap_for_role(self, role_name: str) -> Optional[str]:
        """Get learning roadmap for a role."""
        role = self.get_role(role_name)
        if role:
            return role.get('roadmap')
        return None
    
    def search_roles(self, query: str) -> List[dict]:
        """Search roles by keyword."""
        if not self._loaded:
            self.load()
        
        query_lower = query.lower()
        results = []
        
        for role_name, role_data in self.roles.items():
            if query_lower in role_name:
                results.append(role_data)
            elif query_lower in role_data.get('sector', '').lower():
                results.append(role_data)
            elif any(query_lower in skill.lower() for skill in role_data.get('required_skills', [])):
                results.append(role_data)
        
        return results
    
    def get_all_roles(self) -> List[str]:
        """Get list of all role names."""
        if not self._loaded:
            self.load()
        return [r.get('role') for r in self.roles.values()]


# Global instance
roles_kb = RolesKnowledgeBase()

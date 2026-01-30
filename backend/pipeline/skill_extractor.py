"""
Career Copilot RAG Backend - Step 3: Skill Extractor & Validator
Extracts skills and validates them strictly against the skills catalog.
"""
import logging
from typing import List, Tuple, Dict

from data_loader import data_loader
from models import SemanticResult, SkillValidationResult

logger = logging.getLogger(__name__)


class SkillExtractor:
    """
    Step 3: Extract and validate skills against the catalog.
    
    CRITICAL RULES:
    1. Only skills from skills_catalog_enriched_v2.csv are valid
    2. Discard any skill not found in catalog (no invention)
    3. Prefer specific skills (is_generic=0) over generic ones
    """
    
    SKILL_ALIASES = {
        "statistical analysis": "Statistics",
        "data visualization": "Data Visualization",
        "visualization": "Data Visualization",
        "data mining": "Data Analysis",
        "powerbi": "Power BI",
        "tableau software": "Tableau",
        "python programming": "Python",
        "eda": "Exploratory Data Analysis",
        "pandas library": "pandas",
        "numpy library": "numpy"
    }

    def __init__(self):
        self.data = data_loader
    
    def validate_and_filter(
        self,
        semantic_result: SemanticResult,
    ) -> SkillValidationResult:
        """
        Validate extracted skills against the catalog.
        
        Args:
            semantic_result: Result from semantic layer with extracted skills
            
        Returns:
            SkillValidationResult with only validated skills
        """
    def _apply_track_template(self, validated_skills: List[str], unmatched: List[str], skill_to_domain: Dict[str, str]) -> List[str]:
        """
        Apply strict skill templates for known tracks (e.g., Data Analysis).
        Ensures foundational skills are always present even if not extracted.
        """
        # 1. Data Analysis Track
        da_triggers = ["data analysis", "data analytics", "analysis", "analytics", "تحليل بيانات", "data analyst"]
        is_data_analysis = any(trigger in (s.lower() for s in unmatched) for trigger in da_triggers) or \
                           any(trigger in (unmatched) for trigger in da_triggers) or \
                           any(trigger in (s.lower() for s in validated_skills) for trigger in da_triggers)

        if is_data_analysis:
            logger.info("Applying 'Data Analysis' Track Template - Enforcing Core Skills")
            core_da_skills = ["Microsoft Excel", "SQL", "Python", "Statistics", "Data Visualization", "Power BI"]
            for core in core_da_skills:
                norm = self._validate_skill(core)
                if norm and norm not in validated_skills:
                     validated_skills.append(norm)
                     skill_to_domain[norm] = "Data Analysis"

        # 2. Sales Manager Template (Priority over Soft Skills)
        sales_triggers = ["sales manager", "مدير مبيعات", "sales lead", "head of sales", "sales director"]
        is_sales_manager = any(trigger in (s.lower() for s in (unmatched + validated_skills)) for trigger in sales_triggers) or \
                           any(trigger in (s.lower() for s in unmatched) for trigger in sales_triggers)

        if is_sales_manager:
            logger.info("Applying 'Sales Manager' Track Template - Enforcing 50/50 Split")
            # Mix of Hard Sales Skills + Management
            # Note: We prioritize skills that map to course categories like "Sales", "Business Fundamentals"
            core_sales_skills = [
                "Sales", "Negotiation", "CRM", "Business Development", # Sales side
                "Leadership", "Team Management", "Strategic Planning"  # Manager side
            ]
            for core in core_sales_skills:
                 norm = self._validate_skill(core)
                 if norm and norm not in validated_skills:
                      validated_skills.append(norm)
                      # Force domain mapping for clean UI grouping
                      if core in ["Sales", "Negotiation", "CRM", "Business Development"]:
                          skill_to_domain[norm] = "Sales Strategy"
                      else:
                          skill_to_domain[norm] = "Management"
            
            # CRITICAL: Return early to prevent Soft Skills overwrite
            return validated_skills

        # 3. Soft Skills Track (Only if NO specific role matched)
        soft_triggers = ["soft skills", "مهارات ناعمة", "communication", "تواصل", "leadership", "قيادة", "teamwork", "تعاون"]
        is_soft_skills = any(trigger in (s.lower() for s in (unmatched + validated_skills)) for trigger in soft_triggers)

        if is_soft_skills:
            logger.info("Applying 'Soft Skills' Track Template - Enforcing Core Skills")
            core_soft_skills = ["Communication", "Leadership", "Teamwork", "Problem Solving", "Emotional Intelligence"]
            for core in core_soft_skills:
                norm = self._validate_skill(core)
                if norm and norm not in validated_skills:
                     validated_skills.append(norm)
                     skill_to_domain[norm] = "Soft Skills"
            
        return validated_skills

    def validate_and_filter(self, semantic_result: SemanticResult) -> SkillValidationResult:
        """
        Validate extracted skills against the catalog and filter invalid ones.
        Returns a structured result with validated skills and domain mapping.
        """
        extracted = semantic_result.extracted_skills or []
        
        validated_skills = []
        skill_to_domain = {}
        unmatched = []
        
        for skill in extracted:
            normalized = self._validate_skill(skill)
            if normalized:
                validated_skills.append(normalized)
                # Get domain for the skill
                skill_info = self.data.get_skill_info(normalized)
                if skill_info:
                    domain = skill_info.get('domain', 'General')
                    skill_to_domain[normalized] = domain
            else:
                unmatched.append(skill)
        
        # 2. Production V2: Apply Track Templates (Data Analysis, etc)
        validated_skills = self._apply_track_template(validated_skills, unmatched, skill_to_domain)

        # Sort by specificity (non-generic first)
        validated_skills = self._prioritize_specific(validated_skills)
        
        if unmatched:
            logger.info(f"Discarded unmatched skills: {unmatched}")
        
        return SkillValidationResult(
            validated_skills=validated_skills,
            skill_to_domain=skill_to_domain,
            unmatched_terms=unmatched,
        )
    
    def _validate_skill(self, skill: str) -> str | None:
        """
        Validate a single skill against the catalog.
        Returns normalized skill name or None if not found.
        """
        # User Fix 3: Check Aliases first (Normalize input first using centralized logic)
        from data_loader import DataLoader
        cleaned_skill = DataLoader.normalize_skill(skill)
        
        # Check explicit aliases in Extractor first (if any defined locally)
        if cleaned_skill in self.SKILL_ALIASES:
             cleaned_skill = self.SKILL_ALIASES[cleaned_skill]
             cleaned_skill = DataLoader.normalize_skill(cleaned_skill)

        return self.data.validate_skill(cleaned_skill)
    
    def _prioritize_specific(self, skills: List[str]) -> List[str]:
        """
        Sort skills to prioritize specific ones over generic.
        Specific skills (is_generic=0) come first.
        """
        specific = []
        generic = []
        
        for skill in skills:
            skill_info = self.data.get_skill_info(skill)
            if skill_info and skill_info.get('is_generic', 0) == 1:
                generic.append(skill)
            else:
                specific.append(skill)
        
        return specific + generic
    
    def find_related_skills(self, skill: str, limit: int = 5) -> List[str]:
        """
        Find skills related to a given skill (same domain).
        Useful for expanding search when few results are found.
        """
        skill_info = self.data.get_skill_info(skill)
        if not skill_info:
            return []
        
        domain = skill_info.get('domain')
        if not domain or self.data.skills_df is None:
            return []
        
        # Find other skills in same domain
        same_domain = self.data.skills_df[
            self.data.skills_df['domain'] == domain
        ]['skill_norm'].str.lower().tolist()
        
        # Exclude the original skill and limit results
        related = [s for s in same_domain if s != skill.lower()][:limit]
        return related
    
    def suggest_skills_for_role(self, role: str) -> List[str]:
        """
        Suggest skills typically needed for a role.
        Supports English, Arabic, Franco-Arab (Arabizi), and mixed language queries.
        """
        role_lower = role.lower()
        
        # Comprehensive role to skill mappings (English, Arabic, Franco-Arab)
        role_mappings = {
            # Tech Roles - English
            'data analyst': ['data analysis', 'excel', 'sql', 'python', 'statistics', 'power bi', 'tableau'],
            'data scientist': ['machine learning', 'python', 'statistics', 'deep learning', 'data analysis'],
            'software engineer': ['programming', 'python', 'algorithms', 'system design', 'databases'],
            'web developer': ['html', 'css', 'javascript', 'react', 'node.js', 'web development'],
            'frontend developer': ['html', 'css', 'javascript', 'react', 'vue.js', 'angular'],
            'backend developer': ['python', 'node.js', 'java', 'sql', 'api', 'databases'],
            'full stack developer': ['html', 'css', 'javascript', 'react', 'node.js', 'databases', 'api'],
            'full stack': ['html', 'css', 'javascript', 'react', 'node.js', 'databases', 'api'],
            'mobile developer': ['android', 'ios', 'flutter', 'react native', 'mobile development'],
            'devops engineer': ['docker', 'kubernetes', 'ci/cd', 'linux', 'aws', 'cloud'],
            'devops': ['docker', 'kubernetes', 'ci/cd', 'linux', 'cloud'],
            'ai engineer': ['machine learning', 'deep learning', 'python', 'neural networks'],
            'machine learning engineer': ['machine learning', 'python', 'deep learning', 'tensorflow'],
            
            # Management Roles - English
            'engineering manager': ['leadership', 'team management', 'agile', 'project management', 'programming', 'system design'],
            'tech lead': ['leadership', 'programming', 'system design', 'code review', 'agile'],
            'technical lead': ['leadership', 'programming', 'system design', 'code review', 'agile'],
            'team lead': ['leadership', 'team management', 'communication', 'project management'],
            'project manager': ['project management', 'agile', 'scrum', 'leadership', 'communication'],
            'product manager': ['product management', 'agile', 'user experience', 'analytics'],
            'program manager': ['project management', 'leadership', 'strategic planning', 'communication'],
            'cto': ['leadership', 'system design', 'strategic planning', 'technology management'],
            'vp engineering': ['leadership', 'strategic planning', 'team management', 'technology management'],
            
            # Business Roles - English
            'marketing manager': ['marketing', 'digital marketing', 'social media', 'seo', 'analytics'],
            'sales manager': ['sales', 'negotiation', 'communication', 'crm', 'leadership'],
            'hr manager': ['human resources', 'recruitment', 'training', 'performance management'],
            'business analyst': ['business analysis', 'data analysis', 'excel', 'sql', 'communication'],
            'ui/ux designer': ['user experience', 'user interface', 'figma', 'design thinking'],
            'designer': ['design', 'user experience', 'user interface', 'figma'],
            'content creator': ['content creation', 'video editing', 'storytelling', 'social media marketing', 'copywriting'],
            
            # Arabic Roles - عربي
            'مبرمج': ['programming', 'python', 'javascript', 'web development'],
            'مهندس برمجيات': ['programming', 'python', 'algorithms', 'system design'],
            'مطور ويب': ['html', 'css', 'javascript', 'web development'],
            'مطور': ['programming', 'web development', 'javascript'],
            'محلل بيانات': ['data analysis', 'excel', 'sql', 'python', 'statistics'],
            'عالم بيانات': ['machine learning', 'python', 'statistics', 'deep learning'],
            'مدير مشروع': ['project management', 'agile', 'leadership', 'communication'],
            'مدير منتج': ['product management', 'agile', 'user experience'],
            'مدير مبيعات': ['sales strategy', 'negotiation', 'team management', 'crm', 'business development', 'leadership', 'sales operations'],
            'مدير تسويق': ['marketing', 'digital marketing', 'social media'],
            'مدير موارد بشرية': ['human resources', 'recruitment', 'training'],
            
            # Management + Tech Combo - Arabic (مثل "مدير مبرمجين")
            'مدير مبرمجين': ['leadership', 'team management', 'programming', 'agile', 'project management', 'code review'],
            'مدير فريق برمجة': ['leadership', 'team management', 'programming', 'agile', 'project management'],
            'مدير تطوير': ['leadership', 'software development', 'agile', 'project management', 'team management'],
            'قائد فريق': ['leadership', 'team management', 'communication', 'project management'],
            'مدير تقني': ['leadership', 'system design', 'programming', 'technology management'],
            'مدير هندسة': ['leadership', 'team management', 'system design', 'programming', 'agile'],
            
            # Franco-Arab (Arabizi) - فرانكو
            'developer': ['programming', 'web development', 'javascript', 'python'],
            'programmer': ['programming', 'python', 'javascript'],
            'manager': ['leadership', 'team management', 'communication', 'project management'],
            'leader': ['leadership', 'team management', 'communication'],
            'analyst': ['data analysis', 'excel', 'sql'],
        }
        
        # Find matching role (supports partial matching)
        suggested = []
        for role_key, skills in role_mappings.items():
            # Check for partial match in both directions
            if role_key in role_lower or role_lower in role_key:
                suggested.extend(skills)
                break
            # Check for word overlap
            role_words = set(role_lower.split())
            key_words = set(role_key.split())
            if role_words & key_words:  # If any word matches
                suggested.extend(skills)
                break
        
        # If no direct match, try semantic matching for compound roles
        if not suggested:
            # Check for leadership/management + tech keywords
            management_keywords = ['مدير', 'قائد', 'lead', 'manager', 'head', 'رئيس']
            tech_keywords = ['مبرمج', 'برمجة', 'developer', 'programmer', 'engineering', 'تطوير', 'tech']
            
            has_management = any(kw in role_lower for kw in management_keywords)
            has_tech = any(kw in role_lower for kw in tech_keywords)
            
            if has_management and has_tech:
                # Engineering Manager type role
                suggested = ['leadership', 'team management', 'programming', 'agile', 'project management', 'code review', 'system design']
            elif has_management:
                suggested = ['leadership', 'team management', 'communication', 'project management']
            elif has_tech:
                suggested = ['programming', 'python', 'javascript', 'web development']
        
        # Validate each suggested skill against catalog
        validated = []
        for skill in suggested:
            normalized = self._validate_skill(skill)
            if normalized and normalized not in validated:
                validated.append(normalized)
        
        return validated


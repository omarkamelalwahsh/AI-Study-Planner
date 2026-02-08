"""
Career Copilot RAG Backend - Step 5: Relevance Guard
Filters out irrelevant results before displaying to user.
"""
import logging
from typing import List, Optional

from models import IntentType, IntentResult, CourseDetail, SkillValidationResult, SemanticResult

logger = logging.getLogger(__name__)


class RelevanceGuard:
    """
    Step 5: Filter irrelevant courses before response.
    
    CRITICAL QUESTION: "Does this serve the user's question directly?"
    
    Rules:
    1. Remove courses unrelated to user's domain/intent
    2. Remove generic soft skills unless explicitly requested
    3. Apply domain-based filtering
    """
    
    # Categories considered "generic soft skills"
    SOFT_SKILL_CATEGORIES = {
        'soft skills',
        'personal development',
        'general',
        'health & wellness',
    }
    
    # Keywords that indicate user wants soft skills
    SOFT_SKILL_INDICATORS = {
        'soft skills', 'مهارات ناعمة', 'communication', 'تواصل',
        'leadership', 'قيادة', 'personal development', 'تطوير ذاتي',
    }
    
    def filter(
        self,
        courses: List[CourseDetail],
        intent_result: IntentResult,
        skill_result: SkillValidationResult,
        user_message: str,
        previous_domains: Optional[set] = None,
        semantic_result: Optional[SemanticResult] = None
    ) -> List[CourseDetail]:
        """
        Filter courses to ensure relevance to user's query.
        
        Args:
            courses: Initial list of retrieved courses
            intent_result: User's intent classification
            skill_result: Validated skills
            user_message: Original user message
            previous_domains: Domains from previous turn for context persistence
            
        Returns:
            Filtered list of relevant courses
        """
        if not courses:
            return []
        
        # Check if user explicitly wants soft skills
        wants_soft_skills = self._wants_soft_skills(user_message)
        
        # Get user's primary domain(s) from skill results
        user_domains = set(skill_result.skill_to_domain.values())
        if previous_domains:
             # Merge with previous domains to allow continuity
             user_domains.update({str(d).lower() for d in previous_domains})
        
        # Merged Intent: Skip strict axes filtering for roadmaps
        guidance_intents = [IntentType.CAREER_GUIDANCE]
        
        # 1. Resolve Data-Driven Track/Categories (V16 Production Rule)
        from pipeline.track_resolver import track_resolver
        
        track_decision = track_resolver.resolve_track(user_message, semantic_result, intent_result)
        allowed_categories = set(track_decision.allowed_categories)
        
        # Priority 3: Semantic Axes (Dynamic but catalog-constrained) - MERGE with Track Categories
        if semantic_result and hasattr(semantic_result, 'axes'):
            for axis in semantic_result.axes:
                 cats = axis.get("categories", [])
                 # Only add if valid in data
                 cats = [c for c in cats if c in allowed_categories or not allowed_categories] # If track is strict, respect it?
                 # Actually, for semantic axes, we should validate them against data loader too
                 from data_loader import data_loader
                 real_cats = set(data_loader.get_all_categories())
                 for c in cats:
                     # Fuzzy match to real category names
                     match = next((rc for rc in real_cats if rc.lower() == c.lower()), None)
                     if match:
                         allowed_categories.add(match)

        # Atomic fallback: if axis requested "not_in_catalog"
        if semantic_result and not semantic_result.is_in_catalog:
             logger.warning(f"Domain honesty check: {semantic_result.missing_domain} not in catalog.")

        logger.info(f"Production Whitelist (Track: {track_decision.track_name}): {list(allowed_categories)}")

        # V17: Use normalize_category for consistent comparison
        from data_loader import data_loader
        allowed_norm = {data_loader.normalize_category(c) for c in allowed_categories}
        
        filtered = []
        for course in courses:
            # 1. Hard Whitelist Check (Category-only retrieval)
            if allowed_categories:
                cat_norm = data_loader.normalize_category(course.category or "")
                if cat_norm not in allowed_norm:
                    continue

            # 2. Check relevance using context
            if self._is_relevant(course, user_domains, wants_soft_skills, intent_result, skill_result, user_message):
                 # 3. Axis Overlap Gate
                 if hasattr(intent_result, 'search_axes') and intent_result.search_axes and intent_result.intent not in guidance_intents:
                      overlap_score = self._check_overlap(course, intent_result.search_axes)
                      if overlap_score > 0:
                           filtered.append(course)
                 else:
                      filtered.append(course)

        # 4. Strict Tech Topic Filters (Anti-Drift V3)
        # REMOVED: potential_domain logic is now handled by TrackResolver's allowed_categories
        # If the track is "Backend", only backend categories are in allowed_categories, so frontend courses are already filtered out above.
        
        # 5. STRICT TOPIC FILTERING (Post-Overlap)
        target_topic = intent_result.specific_course or intent_result.slots.get("topic")
        # Only apply if we have a specific target topic and it's not too broad (heuristic: len > 2)
        # NUCLEAR RULE: Do NOT apply strict keyword filter for Guidance/Learning Paths as they are broad
        if target_topic and len(target_topic) > 2 and intent_result.intent not in guidance_intents:
             # But don't filter if topic implies a category (e.g., "programming")
             if target_topic.lower() not in ["programming", "development", "it", "music", "business", "marketing"]:
                  strict_filtered = self._apply_strict_topic_filter(filtered, target_topic)
                  if strict_filtered:
                       filtered = strict_filtered
                  # V17: Removed dangerous empty fallback. Instead, keep original filtered.

        # 6. Production Domain Guard (V13)
        filtered = self._strict_domain_enforcement(filtered, intent_result)

        # --- V17 RULE 2: No-Zero-Results Fallback ---
        if len(filtered) == 0 and len(courses) > 0:
            logger.warning(f"Zero-Results detected. Raw: {len(courses)}. Applying fallback...")
            # Fallback 1: Keep courses whose normalized category is in allowed_categories
            fallback = [c for c in courses if data_loader.normalize_category(c.category or "") in allowed_norm]
            if fallback:
                filtered = fallback[:6]
                logger.info(f"Zero-Results Fallback 1: Kept {len(filtered)} from whitelist relaxation.")
            else:
                # Fallback 2: Return top-k raw courses labeled as "closest matches"
                import copy
                filtered = []
                for c in courses[:6]:
                    c_copy = copy.deepcopy(c)
                    filtered.append(c_copy)
                logger.info(f"Zero-Results Fallback 2: Returning {len(filtered)} closest matches.")

        logger.info(f"Relevance filter: {len(courses)} → {len(filtered)} courses")
        return filtered

    def _strict_domain_enforcement(self, courses: List[CourseDetail], intent_result: IntentResult) -> List[CourseDetail]:
        """Prevents cross-domain drift for common high-level domains (V14)."""
        role = (intent_result.role or "").lower()
        
        # 1. Sales vs Procurement/Logistics
        if any(kw in role for kw in ["sales", "مبيعات", "بائع"]):
             blacklist = ["procurement", "logistics", "supply chain", "مشتريات", "لوجستيات", "سلاسل الإمداد", "inventory management"]
             return [c for c in courses if not any(b in (str(c.title).lower() + " " + str(c.description_short).lower()) for b in blacklist)]
        
        # 2. Tech vs Management (Strict separation unless a Manager role)
        if any(kw in role for kw in ["developer", "programmer", "مبرمج", "كود", "software"]):
             if "management" not in role and "manager" not in role and "مدير" not in role:
                  blacklist = ["pmp", "agile leadership", "scrum master", "إدارة فرق", "mba", "business fundamentals"]
                  courses = [c for c in courses if not any(b in str(c.title).lower() for b in blacklist)]

        # 3. HR / Soft Skills vs Technical
        if any(kw in role for kw in ["hr", "موارد بشرية", "soft skills", "مهارات ناعمة", "personal development"]):
             blacklist = ["python", "javascript", "react", "sql", "html", "css", "docker", "kubernetes", "aws", "azure"]
             return [c for c in courses if not any(b in str(c.title).lower() for b in blacklist)]

        return courses

    def _apply_frontend_topic_filter(self, courses: List[CourseDetail]) -> List[CourseDetail]:
        """Strictly ensures frontend courses don't drift into backend (SQL, PHP, API)."""
        # Blacklist for Frontend
        backend_only = ["sql", "mysql", "postgres", "php", "laravel", "django", "flask", "node.js express", "api development", "backend", "سيرفر", "داتابيز"]
        
        filtered = []
        for c in courses:
            text = (str(c.title) + " " + str(c.description_short)).lower()
            if not any(b in text for b in backend_only):
                filtered.append(c)
            elif any(kw in text for kw in ["html", "css", "javascript", "react", "frontend", "فرونت"]):
                filtered.append(c) # Keep if it contains both (e.g. "Fullstack")
        return filtered

    def _apply_backend_topic_filter(self, courses: List[CourseDetail], user_message: str) -> List[CourseDetail]:
        """Ensures backend courses are actually backend and handles WordPress exclusion."""
        msg = user_message.lower()
        backend_keywords = [
            "api", "rest", "crud", "database", "sql", "mysql", "postgres", 
            "authentication", "authorization", "backend", "server", "php", 
            "laravel", "django", "flask", "node", "express", ".net", "spring", 
            "oop", "mvc",
            "باك", "باك اند", "سيرفر", "خادم", "قاعدة بيانات", "داتابيز", 
            "تسجيل دخول", "مصادقة", "صلاحيات", "واجهة برمجة"
        ]
        cms_indicators = ["wordpress", "ووردبريس", "plugin", "بلجن"]
        
        # User explicitly wants WordPress?
        wants_cms = any(kw in msg for kw in cms_indicators)
        
        filtered = []
        for c in courses:
            title = str(c.title or "").lower()
            # Handle possible Any type for description fields
            desc_full = str(getattr(c, 'description_full', '') or '')
            desc_short = str(getattr(c, 'description_short', '') or '')
            text = (title + " " + desc_full + " " + desc_short).lower()
            
            # Anti-WordPress Gate
            is_wordpress = any(kw in text for kw in ["wordpress", "ووردبريس"])
            if is_wordpress and not wants_cms:
                continue
                
            # Backend Keyword Gate
            if any(kw in text for kw in backend_keywords):
                filtered.append(c)
            elif wants_cms and is_wordpress:
                filtered.append(c)
                
        return filtered
    
    def _check_overlap(self, course: CourseDetail, axes: List[str]) -> int:
        """Count how many Search Axes keywords appear in course title/description."""
        text = (str(course.title) + " " + str(course.description) + " " + str(course.category)).lower()
        score = 0
        for axis in axes:
             if axis.lower() in text:
                  score += 1
        return score

    def _apply_strict_topic_filter(self, courses: List[CourseDetail], topic: str) -> List[CourseDetail]:
        """
        User Rule 3: STRICT keyword filter.
        If user said 'Python', course MUST contain 'Python' in title, category, or description.
        """
        topic_lower = topic.lower()
        filtered = []
        for c in courses:
            text_blob = (str(c.title) + " " + str(c.category) + " " + str(c.description)).lower()
            if topic_lower in text_blob:
                filtered.append(c)
            # Special case: 'programming' is too broad, but if topic is 'python', we require python.
            # If topic itself is 'programming', then almost anything tech works.
        
        return filtered

    def _is_relevant(
        self,
        course: CourseDetail,
        user_domains: set,
        wants_soft_skills: bool,
        intent_result: IntentResult,
        skill_result: SkillValidationResult = None,
        user_message: str = "",
    ) -> bool:
        """Check if a single course is relevant."""
        category = str(course.category or '').lower()
        title = str(course.title or '').lower()
        description = str(course.description or '').lower()
        
        # If no skills were validated, be VERY strict with any course retrieved
        if skill_result and not skill_result.validated_skills and skill_result.unmatched_terms:
            # Check if course title/description has ANY overlap with the unmatched terms
            for term in skill_result.unmatched_terms:
                term_lower = term.lower()
                if term_lower in title or term_lower in description:
                    return True
            
            # If no keyword overlap and no validated skills, this is probably a cross-domain hallucination from retrieval/semantic
            return False

        # Domain Safety Check (Crucial for grounding)
        if skill_result and (skill_result.validated_skills or user_domains):
            # Use user_domains which already includes current + previous context
            allowed_domains = {str(d).lower() for d in user_domains}
            
            # Special case for "Programming" and "Data Security" overlap for tech keywords
            tech_keywords = {'python', 'javascript', 'php', 'sql', 'mysql', 'html', 'css', 'programming', 'code', 'database'}
            if any(k in title or k in description for k in tech_keywords):
                allowed_domains.update({'programming', 'data security', 'technology applications', 'web development'})
            
            # If course category is not in allowed domains, it's a cross-domain noise
            # V6 Fix: Allow partial matches (e.g. "Sales Strategy" matches "Sales")
            if category and not any(d in category or category in d for d in allowed_domains):
                # If it's a soft skill and not requested, we already filter below, 
                # but this also catches other unrelated domains (e.g., Banking, Public Speaking)
                return False

        # If user explicitly wants soft skills, don't filter them out
        if wants_soft_skills:
            return True
        
        # If course is soft skills and user didn't ask for them, filter out
        if category in self.SOFT_SKILL_CATEGORIES:
            # If user has a specific technical domain, soft skills are probably noise
            if user_domains and not any(d.lower() in self.SOFT_SKILL_CATEGORIES for d in user_domains):
                return False
        
        return True
    
    def _wants_soft_skills(self, message: str) -> bool:
        """Check if user explicitly wants soft skills."""
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in self.SOFT_SKILL_INDICATORS)
    
    def limit_results(
        self,
        courses: List[CourseDetail],
        max_courses: int = 10,
    ) -> List[CourseDetail]:
        """
        Apply display limit to courses.
        Note: We return all for retrieval but may limit for display.
        """
        return courses[:max_courses]

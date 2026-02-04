"""
Career Copilot RAG Backend - Step 6: Response Builder
Dynamic response generation based on intent type.
"""
import logging
from typing import List, Optional, Dict
import copy
import json

from llm.base import LLMBase
from models import (
    IntentType, IntentResult, CourseDetail, ProjectDetail, 
    SkillValidationResult, SkillGroup, LearningPlan, WeeklySchedule, LearningItem,
    CVDashboard, SkillItem, CatalogBrowsingData, CategoryDetail, SemanticResult
)

logger = logging.getLogger(__name__)

def user_asked_for_plan(msg: str) -> bool:
    m = msg.lower()
    triggers = ["plan", "roadmap", "timeline", "step by step", "learning path", "path",
                "خطة", "مسار", "جدول", "جدول زمني", "خطوات", "ابدأ خطة", "اعملّي خطة"]
    return any(t in m for t in triggers)

def user_asked_for_projects(msg: str) -> bool:
    m = msg.lower()
    triggers = ["project", "projects", "portfolio", "practice", "tasks",
                "مشاريع", "بورتفوليو", "تطبيق", "تمارين", "تاسكات"]
    return any(t in m for t in triggers)


CV_ANALYSIS_SYSTEM_PROMPT = """SYSTEM: You are Career Copilot's CV Analysis Engine.
GOAL:
Analyze the uploaded CV and produce a dashboard-ready JSON output that:
1) scores the CV, highlights strengths and gaps,
2) ALWAYS produces course recommendation needs (skills to learn) even if the candidate is strong,
3) recommends only courses from the internal catalog (the backend will attach the actual courses),
4) produces portfolio/practice ideas ONLY when they are relevant,
5) never says "check dashboard" unless you actually return dashboard data.

IMPORTANT CONSTRAINTS:
- You MUST output ONLY valid JSON (no markdown, no extra text).
- You MUST NOT invent course titles. You only output "course_needs" (skills/topics), and the backend will map to catalog courses.
- You MUST remain role-relevant and avoid unrelated drift.
- NO bias: do not assume the user's background, education, or industry beyond the CV text and provided target role.

OUTPUT POLICY (CRITICAL):
A) Always output BOTH:
   - portfolio_actions (projects/practice) AND
   - course_needs (skills/topics that should be covered by courses)
   Even if the candidate is "strong".
B) If overall_score >= 80:
   - Do NOT stop at praise.
   - Provide "advanced specialization" course_needs (e.g., MLOps, deployment, evaluation, system design) + "ATS polish".
C) If some skill is already strong, you may still recommend advanced courses for depth (e.g., "SQL -> window functions"), but mark them as "growth" not "gap".
D) If the catalog skill vocab is provided, normalize to it; if not, return skills in clean English canonical form.

ANALYSIS STEPS:
1) Determine primary_role and secondary_role.
2) Extract skills into: strong_skills, developing_skills, missing_skills.
3) Score 5 dimensions (0-100): skills_match, experience, impact, ats_readiness, communication.
4) Build course_needs:
   - MUST include at least 6 items total:
     - 2-3 "gap" items (missing)
     - 2-3 "growth" items (advanced depth)
     - 1 "career leverage" item (e.g., system design)
   Each item: { "topic": "...", "priority": "high", "type": "gap|growth", "rationale": "..." }
5) Build portfolio_actions (3 items):
   - Role-relevant, feasible projects.
6) Build ATS keywords:
   - missing_keywords must be tokenized (separate words).

STRICT OUTPUT JSON SCHEMA:
{
  "candidate": { "name": "...", "targetRole": "...", "seniority": "..." },
  "score": { "overall": 0, "skills": 0, "experience": 0, "projects": 0, "marketReadiness": 0, "ats": 0 },
  "roleFit": { "summary": "...", "detectedRoles": ["..."] },
  "skills": {
      "strong": [{"name": "", "confidence": 0.0}],
      "weak": [{"name": "", "confidence": 0.0}],
      "missing": [{"name": "", "confidence": 0.0}]
  },
  "course_needs": [
      { "topic": "...", "priority": "high", "type": "gap|growth", "rationale": "..." }
  ],
  "portfolio_actions": [
      { "title": "...", "level": "Advanced", "description": "...", "skills_targeted": ["..."], "deliverables": ["..."] }
  ],
  "atsChecklist": [ { "id": "1", "text": "...", "done": true } ],
  "recommendations": ["..."]
}"""

RESPONSE_SYSTEM_PROMPT = """SYSTEM: Career Copilot for Zedny — Production System Prompt (v3.0)

You are a human mentor specializing in career guidance for Zedny.
Your job is to guide users to the right career track and recommend ONLY courses from our catalog.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GLOBAL RULES (NO EXCEPTIONS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. BEHAVE LIKE A HUMAN MENTOR: Be supportive, professional, and helpful. 
2. NO TECHNICAL ERRORS: Never say "Error" or "Technical error". If something fails, ask a helpful question.
3. LANGUAGE MIRRORING: If user says Arabic -> respond ONLY in Arabic. If English -> English.
4. SINGLE INTENT: Every response must follow exactly ONE intent.
5. NO HALLUCINATION: Only recommend courses that exist in the provided list.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPLORATION FLOW ( Zedny 4-Step )
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trigger: User is unsure or says (مش عارف أختار / أبدأ منين / ساعدني).
Step 1: Ask: "هدفك إيه؟ A) شغل جديد B) ترقية C) تغيير مجال"
Step 2: Ask Interest: "تحب أكتر: 1) Programming 2) Data 3) Marketing 4) Business 5) Design"
Step 3: Return specific catalog categories related to their interest.
Step 4: Switch to COURSE_SEARCH once they pick a track.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COURSE SEARCH / LEARNING PLAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- COURSE_SEARCH: Show Top 3 ONLY. Briefly explain why they fit.
- LEARNING_PLAN: Slot-fill Duration/Time first. Then provide structured day-by-day tasks + weekly deliverable. Use courses from selected topic.

STRICT JSON SCHEMA:
{
  "intent": "<INTENT>",
  "language": "ar" | "en",
  "answer": "<Mentor text>",
  "ask": null | { "question": "...", "choices": ["..."] },
  "learning_plan": null | { ... },
  "courses": [], "projects": [],
  "flow_state_updates": { ... }
}
"""

LEARNING_PATH_SYSTEM_PROMPT = """You are Career Copilot. When intent = LEARNING_PATH:

A) If duration or daily_time is missing:
- Ask exactly: "تحب الخطة لمدة قد إيه؟ (أسبوع/أسبوعين/شهر/شهرين) + وقتك يوميًا قد إيه؟ (ساعة/ساعتين/3+)"
- STOP and return null for learning_plan. Use the exact choices provided to you in the rules.

B) If duration and daily_time are provided:
- Provide a structured plan in the "schedule" field.
- Each item: { "day_or_week": "...", "topics": [...], "tasks": [...], "deliverable": "..." }
- Use the user's language.
"""


class ResponseBuilder:
    """
    Step 6: Build dynamic response based on intent.
    """
    
    def __init__(self, llm: LLMBase):
        self.llm = llm
        self.last_followup_question = ""

    async def build(
        self,
        intent_result: IntentResult,
        courses: List[CourseDetail],
        skill_result: SkillValidationResult,
        user_message: str,
        context: Optional[dict] = None,
        available_categories: List[str] = [],
        semantic_result: Optional[SemanticResult] = None
    ) -> tuple:
        """
        Main response orchestration (Production V2.0: Strict Flow & Intent Locking).
        """
        from data_loader import data_loader
        is_ar = data_loader.is_arabic(user_message)
        lang = "ar" if is_ar else "en"
        
        # 0. RESOLVE INTENT (Rule 1 Overrides)
        intent = intent_result.intent
        
        # 1. FOLLOW-UP / PAGINATION (Rule 6)
        is_follow_up = intent == IntentType.FOLLOW_UP or any(kw in user_message.lower() for kw in ["more", "أظهر المزيد", "تانية", "كمان"])
        if is_follow_up and context and context.get("all_relevant_course_ids"):
            intent = IntentType.FOLLOW_UP
            # Logic for follow-up is partially in main.py, but we ensure here too
            if not courses:
                msg = "تمام، تحب أجيبلك كورسات في إيه بالظبط؟" if is_ar else "What exactly do you want to learn more about?"
                return msg, [], [], [], None, None, [], None, "answer_only", msg, "FOLLOW_UP", None

        # 2. CATALOG BROWSING (LLM-FREE)
        if intent == IntentType.CATALOG_BROWSING:
             return self._build_catalog_browsing_response(user_message, is_ar)

        # 3. PROJECT IDEAS (Rule 1C, 2-Project)
        if intent == IntentType.PROJECT_IDEAS:
             return await self._build_project_ideas_response(user_message, intent_result.topic, courses, is_ar)

        # 4. LEARNING PATH (Rule 1B, 2-Plan, 3-Duration)
        if intent == IntentType.LEARNING_PATH:
             return await self._build_learning_path_response(user_message, intent_result, courses, is_ar, context)

        # 5. CAREER GUIDANCE (Rule 1D, 2-Guidance)
        if intent == IntentType.CAREER_GUIDANCE:
             return await self._build_career_guidance_response(user_message, intent_result, courses, is_ar)

        # 6. EXPLORATION (Rule 1F, 2-Exploration)
        if intent in [IntentType.EXPLORATION, IntentType.EXPLORATION_FOLLOWUP]:
             return self._handle_exploration_flow(user_message, context, is_ar)

        # 7. COURSE SEARCH (Rule: Top 3 only + Fitting Explanation)
        # Prepare course context for LLM
        courses_data = [
            {"course_id": str(c.course_id), "title": c.title, "instructor": c.instructor, "category": c.category, "level": c.level}
            for c in courses[:3]
        ]
        
        try:
            response = await self.llm.generate_json(
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                prompt=f"User Message: {user_message}\nIntent: {intent.value if hasattr(intent, 'value') else intent}\nRetrieved Courses: {json.dumps(courses_data)}",
                temperature=0.3
            )
            
            answer = str(response.get("answer") or ("أرشحلك الكورسات دي عشان تبدأ طريقك:" if is_ar else "I recommend these courses to start your journey:"))
            
            # Map selected courses with why_recommended (Fitting Explanation)
            final_courses = []
            for c_obj in courses[:3]:
                c_copy = copy.deepcopy(c_obj)
                # If LLM didn't provide specific 'why', use a default humanized explanation
                c_copy.why_recommended = "بيتوافق مع مهاراتك وأهدافك اللي ذكرتها." if is_ar else "Fits your goals and skills perfectly."
                final_courses.append(c_copy)
                
            return answer, [], final_courses, [], None, None, courses, None, "courses_only", None, intent.value if hasattr(intent, 'value') else intent, None

        except Exception as e:
            logger.error(f"Build failed: {e}")
            fallback_msg = "تمام، بس محتاج أعرف أكتر عن هدفك عشان أرشحلك أحسن حاجة؟" if is_ar else "Got it, but I'd love to know more about your goal to give you the best advice."
            return fallback_msg, [], [], [], None, None, [], None, "fallback", "", intent.value if hasattr(intent, 'value') else intent, None

    def _build_catalog_browsing_response(self, message: str, is_ar: bool) -> tuple:
        """Requirement A: 100% Data-Driven (No LLM). Guided Menu + Grouping."""
        from data_loader import data_loader
        msg = message.lower()
        all_cats = data_loader.get_all_categories()
        
        # 1. Zedny Rule: Exploration Domain List Fallback
        undecided_kws = ["مش عارف اختار", "ساعدني اختار", "محتار", "اختارلي", "مش محدد", "أي مجال", "أى مجال"]
        if any(kw in msg for kw in undecided_kws):
             # These 4 exact domains as per rule
             target_domains = ["Programming", "Marketing", "Business", "Design"]
             cats = [CategoryDetail(name=d, why="مجال متاح") for d in target_domains]
             answer = "لا تقلق، أنا هنا لمساعدتك. إليك المجالات المتاحة لدينا، اختر واحداً لنبدأ الجولة:" if is_ar else "No worries, I'm here to help. Here are our available domains, pick one to start:"
             f_q = "اختار مجال من دول:" if is_ar else "Pick one of these domains:"
             return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING", None

        # 2. Umbrella groups for better UX
        programming_umbrella = ["Technology Applications", "Computer Science", "Backend Development", "Frontend Development"]
        
        if any(kw in msg for kw in ["برمجة", "programming", "developer", "software"]):
             cats = [CategoryDetail(name=c, why="تخصص برمجي متاح") for c in programming_umbrella if c in all_cats]
             answer = "عالم البرمجة واسع! دي التخصصات المتاحة عندنا:" if is_ar else "The programming world is huge! Here are our tracks:"
             f_q = "تحب تركز على Web ولا Mobile ولا Security؟" if is_ar else "Focus on Web, Mobile, or Security?"
             return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING", None

        # 3. "I don't know" - Guided Discovery
        if any(kw in msg for kw in ["مش عارف", "don't know", "معرفش"]):
             top_6 = all_cats[:6] # Deterministic top 6
             cats = [CategoryDetail(name=c, why="مجال مشهور ومنصح به") for c in top_6]
             answer = "ولا يهمك! دي أكتر 6 مجالات مطلوبة عندنا. اختار اللي يشدك أكتر:" if is_ar else "No worries! Here are the top 6 trending tracks. Pick one:"
             f_q = "إيه أكتر مجال مهتم بيه من دول؟" if is_ar else "Which area interests you most?"
             return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING", None

        # 4. Default: Full List
        cats = [CategoryDetail(name=c, why="تصفح القسم") for c in all_cats]
        answer = "دي كل الأقسام المتاحة عندنا. اختار أي واحد وهطلعلك تفاصيله:" if is_ar else "Here are all available categories. Pick one to explore:"
        f_q = "تختار أي قسم؟" if is_ar else "Which category would you like to explore?"
        return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING", None

    def _handle_exploration_flow(self, user_msg: str, context: dict, is_ar: bool) -> tuple:
        """
        Zedny 4-Step Exploration Flow (Rule: Global Priority).
        1) Goal -> 2) Interest -> 3) Catalog categories -> 4) COURSE_SEARCH
        """
        exp_state = context.get("exploration", {}) if context else {}
        if not exp_state: exp_state = {"step": 0}
        
        step = exp_state.get("step", 0)
        user = user_msg.lower()
        from models import ChoiceQuestion
        
        # Step 1: Goal
        if step == 0:
            exp_state["step"] = 1
            q = "هدفك إيه؟" if is_ar else "What is your goal?"
            choices = ["شغل جديد", "ترقية", "تغيير مجال"] if is_ar else ["New Job", "Promotion", "Career Shift"]
            ask = ChoiceQuestion(question=q, choices=choices)
            answer = "أهلاً بيك! أنا كارير كوبايلوت ومكاني هنا عشان أساعدك تختار طريقك. قولي، هدفك إيه حالياً؟" if is_ar else "Hello! I'm your Career Copilot, here to guide you. Tell me, what's your primary goal?"
            state_updates = {"exploration": exp_state, "active_flow": "EXPLORATION_FLOW"}
            return answer, [], [], [], None, None, [], None, "exploration_questions", ask, "EXPLORATION", state_updates

        # Step 2: Interest (after Step 1)
        if step == 1:
            # Capture goal
            if any(w in user for w in ["شغل", "job"]): exp_state["goal"] = "Job"
            elif any(w in user for w in ["ترقية", "promo"]): exp_state["goal"] = "Promotion"
            else: exp_state["goal"] = "Career Shift"
            
            exp_state["step"] = 2
            q = "تحب أكتر:" if is_ar else "What interests you most?"
            choices = ["Programming", "Data", "Marketing", "Business", "Design"]
            ask = ChoiceQuestion(question=q, choices=choices)
            answer = "عظيم جداً. قوللي بقى، إيه أكتر مجال بيشدك من دول؟" if is_ar else "Great! Which of these fields interests you the most?"
            state_updates = {"exploration": exp_state, "active_flow": "EXPLORATION_FLOW"}
            return answer, [], [], [], None, None, [], None, "exploration_questions", ask, "EXPLORATION", state_updates

        # Step 3: Catalog Categories (after Step 2)
        if step == 2:
            # Capture interest
            interest = "Programming"
            if "data" in user or "بيانات" in user: interest = "Data Analysis"
            elif "marketing" in user or "تسويق" in user: interest = "Marketing"
            elif "business" in user or "بيزنس" in user: interest = "Business Strategy"
            elif "design" in user or "تصميم" in user: interest = "Graphic Design"
            exp_state["interest"] = interest
            
            # Get real categories from catalog
            from data_loader import data_loader
            suggested_cats = data_loader.suggest_categories_for_topic(interest, top_n=5)
            
            exp_state["step"] = 3
            q = "أي مجال فرعي تحب تبدأ فيه؟" if is_ar else "Which sub-track would you like to explore?"
            ask = ChoiceQuestion(question=q, choices=suggested_cats)
            answer = f"بناءً على ميولك للـ {interest}، أنصحك تختار تخصص من دول عشان نلاقي الكورسات المناسبة ليك:" if is_ar else f"Based on your interest in {interest}, I recommend picking one of these tracks to find the right courses:"
            
            state_updates = {"exploration": exp_state, "active_flow": "EXPLORATION_FLOW"}
            return answer, [], [], [], None, None, [], None, "catalog_exploration", ask, "EXPLORATION", state_updates

        # Final Transition: Switch to COURSE_SEARCH (after Step 3)
        # Clear exploration state
        state_updates = {"exploration": {}, "active_flow": None}
        answer = "تمام، هطلعلك أهم الكورسات في التخصص اللي اخترته." if is_ar else "Got it! Here are the best courses for your selected track."
        return answer, [], [], [], None, None, [], None, "answer_only", None, "COURSE_SEARCH", state_updates

    async def _build_project_ideas_response(self, user_msg: str, topic: Optional[str], courses: List[CourseDetail], is_ar: bool) -> tuple:
        """Generates project ideas using LLM (Rule 1C, 2-Project)."""
        prompt = f"User asks for project ideas. Topic: {topic or 'General'}. Language: {'Arabic' if is_ar else 'English'}."
        try:
            raw_json = await self.llm.generate_json(prompt, system_prompt=RESPONSE_SYSTEM_PROMPT, temperature=0.7)
            projects_data = raw_json.get("projects", [])
            answer = raw_json.get("answer", "أكيد، دي شوية أفكار لمشاريع ممكن تنفذها:" if is_ar else "Here are some project ideas:")
            
            projects = []
            for p in projects_data:
                projects.append(ProjectDetail(
                    title=p.get("title", "Project"),
                    level=p.get("level", "Intermediate"),
                    features=p.get("features", []),
                    stack=p.get("stack", []),
                    deliverable=p.get("deliverable")
                ))
            
            from models import ChoiceQuestion
            ask_data = raw_json.get("ask")
            ask = ChoiceQuestion(**ask_data) if ask_data else None
            
            return answer, projects, [], [], None, None, [], None, "projects_only", ask, "PROJECT_IDEAS", None
            
        except Exception as e:
            logger.error(f"Project ideas failed: {e}")
            return "عذراً، مش قادر أجيب أفكار حالياً.", [], [], [], None, None, [], None, "fallback", None, "PROJECT_IDEAS", None

    async def _build_career_guidance_response(self, user_msg: str, intent_result: IntentResult, courses: List[CourseDetail], is_ar: bool) -> tuple:
        """Generates career advice (Rule 1D, 2-Guidance)."""
        prompt = f"User needs career guidance. Message: {user_msg}\nTopic: {intent_result.topic or 'General'}"
        try:
            raw_json = await self.llm.generate_json(prompt, system_prompt=RESPONSE_SYSTEM_PROMPT, temperature=0.7)
            answer = raw_json.get("answer", "دي شوية خطوات عشان توصل لهدفك:")
            
            from models import ChoiceQuestion
            ask_data = raw_json.get("ask")
            ask = ChoiceQuestion(**ask_data) if ask_data else None
            
            return answer, [], courses[:3], [], None, None, courses, None, "guidance", ask, "CAREER_GUIDANCE", None
        except Exception as e:
            logger.error(f"Guidance failed: {e}")
            return "عذراً، حدث خطأ.", [], [], [], None, None, [], None, "fallback", None, "CAREER_GUIDANCE", None

    async def _build_learning_path_response(self, user_msg: str, intent_result: IntentResult, courses: List[CourseDetail], is_ar: bool, context: Optional[dict] = None) -> tuple:
        """Generates a structured learning plan with Slot Gate (Rule 1B, 2-Plan, 3-Duration)."""
        topic = intent_result.topic or (context.get("last_topic") if context else "General")
        
        # Check Duration and Time
        duration = intent_result.duration
        daily_time = intent_result.daily_time
        
        # 1. Missing Slot Check (Rule: Zedny Slot Filling)
        if not duration or not daily_time:
             from models import ChoiceQuestion
             
             # If both missing, ask duration first
             if not duration:
                 q = "تحب الخطة لمدة قد إيه؟" if is_ar else "How long would you like the plan to be?"
                 choices = ["أسبوع", "أسبوعين", "شهر"] if is_ar else ["1 Week", "2 Weeks", "1 Month"]
             else:
                 # Duration known, ask time
                 q = "وقت قد إيه يوميًا؟" if is_ar else "How much time per day?"
                 choices = ["ساعة", "ساعتين", "3+"] if is_ar else ["1 Hour", "2 Hours", "3+ Hours"]
             
             ask = ChoiceQuestion(question=q, choices=choices)
             ans = "تمام، بس محتاج أعرف تفاصيل أكتر عشان أظبطلك الخطة." if is_ar else "Got it! I just need a few more details to set up your plan."
             return ans, [], [], [], None, None, [], None, "answer_only", ask, "LEARNING_PATH", None

        prompt = f"Topic: {topic}\nDuration: {duration}\nTime: {daily_time}\nCourses: {[c.title for c in courses[:5]]}"
        try:
            raw_json = await self.llm.generate_json(prompt, system_prompt=LEARNING_PATH_SYSTEM_PROMPT, temperature=0.3)
            plan_raw = raw_json.get("learning_plan") or {}
            schedule_raw = plan_raw.get("schedule", [])
            
            schedule = []
            for item in schedule_raw:
                schedule.append(LearningItem(
                    day_or_week=item.get("day_or_week", item.get("day", "Day 1")),
                    topics=item.get("topics", []),
                    tasks=item.get("tasks", []),
                    deliverable=item.get("deliverable")
                ))
            
            final_plan = LearningPlan(
                topic=topic,
                duration=duration or plan_raw.get("duration"),
                time_per_day=daily_time or plan_raw.get("time_per_day"),
                schedule=schedule
            )
            
            answer = raw_json.get("answer", f"دي خطة مذاكرة لـ {topic}:")
            return answer, [], courses[:3], [], final_plan, None, courses, None, "plan_and_courses", None, "LEARNING_PATH", None

        except Exception as e:
            logger.error(f"Learning Path generation failed: {e}")
            msg = "عذراً، حصل مشكلة وأنا بجهز الخطة. جرب تاني كمان شوية."
            return (msg, [], [], [], None, None, [], None, "fallback", "", "LEARNING_PATH", None)

    async def _build_cv_dashboard(self, user_message: str, skill_result: SkillValidationResult) -> tuple:
        """Generate structured CV Dashboard with Rich UI Schema."""
        # Returns (answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard, all_relevant, catalog_b, mode, f_q, intent)
        prompt = f"""User CV Analysis Request:
{user_message[:6000]}

Validated Skills: {', '.join(skill_result.validated_skills)}
Skill Domains: {skill_result.skill_to_domain}

Generate a comprehensive CV Analysis JSON matching this UI schema:

1. candidate: {{ name, targetRole, seniority }}
2. score: {{ overall (0-100), skills, experience, projects, marketReadiness }}
3. roleFit: {{ detectedRoles: [], direction: "", summary: "" }}
4. skills: {{ 
    strong: [{{name, confidence}}], 
    weak: [{{name, confidence}}], 
    missing: [{{name, confidence}}] (Crucial: suggest specific missing tech skills for the target role)
}}
5. radar: [ 
    {{ "area": "Hard Skills", "value": 0-100 }},
    {{ "area": "Experience", "value": 0-100 }},
    {{ "area": "ATS", "value": 0-100 }},
    {{ "area": "Soft Skills", "value": 0-100 }},
    {{ "area": "Impact", "value": 0-100 }}
]
6. projects: [ {{ title, level, description, skills: [] }} ] (Suggest 2-3 specific portfolio projects to fill gaps)
7. atsChecklist: [ {{ id, text, done: boolean }} ] (Evaluate formatting, metrics, keywords)
8. notes: {{ strengths, gaps }}

Ensure strictly valid JSON.
"""
        
        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt="You are an expert Career Coach and CV Analyst. Analyze the CV deeply and provide structured JSON data for the dashboard.",
                temperature=0.4
            )

            # Parse Dashboard
            dashboard_data = CVDashboard(
                candidate=response.get("candidate", {}),
                score=response.get("score", {}),
                roleFit=response.get("roleFit", {}),
                skills=response.get("skills", {"strong": [], "weak": [], "missing": []}),
                radar=response.get("radar", []),
                projects=response.get("projects", []),
                atsChecklist=response.get("atsChecklist", []),
                notes=response.get("notes", {}),
                recommendations=[str(p.get('title', 'Project')) for p in response.get("projects", [])]
            )

            # Standard Chat Response
            answer = f"🔍 **Analysis Complete for {dashboard_data.candidate.get('targetRole', 'your role')}**\n\n" \
                     f"**Score:** {dashboard_data.score.get('overall', 0)}/100\n" \
                     f"**Summary:** {dashboard_data.roleFit.get('summary', '')}\n\n" \
                     f"Check the Dashboard below for a deep dive into your skills and gaps! ⬇️"
            
            # Fix tokenization of keywords
            missing = dashboard_data.skills.missing
            clean_missing = []
            for m in missing:
                 if isinstance(m, dict):
                      name = m.get("name", "")
                      import re
                      if len(name) > 15 and " " not in name: 
                           name = " ".join(re.findall('[A-Z][^A-Z]*', name))
                      m["name"] = name
                      clean_missing.append(m)
                 else:
                      clean_missing.append(m)
            dashboard_data.skills.missing = clean_missing

            # Fetch Courses for "course_needs" from Catalog
            course_needs = response.get("course_needs", [])
            final_courses = []
            from data_loader import data_loader
            
            for need in course_needs:
                 topic = need.get("topic", "")
                 results = data_loader.search_courses_by_title(topic)
                 if not results:
                      skill_info = data_loader.get_skill_info(topic)
                      if skill_info:
                           results = data_loader.get_courses_for_skill(skill_info.get("skill_norm", ""))
                 
                 for c_dict in results[:2]:
                      c_obj = CourseDetail(**c_dict)
                      c_obj.reason = f"{need.get('type', 'Growth').title()}: {need.get('rationale', 'Recommended for you.')}"
                      if c_obj.course_id not in [x.course_id for x in final_courses]:
                           final_courses.append(c_obj)

            # Map Portfolio Actions to Projects
            projects = []
            raw_projects = response.get("projects", [])
            portfolio_acts = response.get("portfolio_actions", [])
            combined_acts = raw_projects + portfolio_acts
            
            for act in combined_acts:
                 projects.append(ProjectDetail(
                      title=act.get("title", act.get("name", "Project")),
                      difficulty=act.get("level", act.get("difficulty", "Intermediate")),
                      description=act.get("description", ""),
                      deliverables=act.get("deliverables", []),
                      suggested_tools=act.get("skills_targeted", act.get("skills", []))
                 ))
            
            if not projects:
                 projects = self._fallback_projects(dashboard_data.candidate.get('targetRole', 'your role'))

            dashboard_data.recommendations = response.get("recommendations", [])

            return answer, projects, final_courses, [], None, dashboard_data, [], None, None, None, "CV_ANALYSIS", None
        except Exception as e:
            logger.error(f"CV Dashboard generation failed: {e}")
            return "عذراً، حدث خطأ أثناء تحليل السيرة الذاتية.", [], [], [], None, None, [], None, None, None, "CV_ANALYSIS", None

    async def build_fallback(
        self,
        user_message: str,
        topic: str
    ) -> tuple:
        """
        Generate a smart fallback response for out-of-scope topics (V18 Fix: Logical Alternatives).
        """
        # V18 FIX 3: Logical Alternatives Table
        # Map missing topics to logical alternatives present in catalog
        LOGICAL_ALTERNATIVES = {
            "blockchain": ["Data Security", "Programming"],
            "crypto": ["Data Security", "Programming"],
            "machine learning": ["Technology Applications", "Programming"],
            "ai": ["Technology Applications", "Programming"],
            "artificial intelligence": ["Technology Applications", "Programming"],
            "cloud": ["Networking", "Data Security"],
            "devops": ["Programming", "Networking"],
            "iot": ["Networking", "Technology Applications"],
            "robotics": ["Technology Applications", "Programming"],
            "game": ["Programming", "Design"],
            "video editing": ["Graphic Design", "Digital Media"],
            "3d": ["Graphic Design", "Digital Media"],
            "architecture": ["Project Management", "Design"],
            "medicine": ["Soft Skills", "Leadership & Management"],
            "law": ["Soft Skills", "Business Fundamentals"],
        }
        
        topic_lower = topic.lower()
        alternatives = []
        
        # Find matches
        for key, cats in LOGICAL_ALTERNATIVES.items():
            if key in topic_lower:
                alternatives = cats
                break
        
        if not alternatives:
            alternatives = ["Programming", "Technology Applications"]  # Safe defaults
        
        # Construct deterministic answer (No LLM to prevent hallucination)
        from data_loader import data_loader
        is_ar = data_loader.is_arabic(user_message)
        
        if is_ar:
            answer = f"""
عذراً، مجال **{topic}** مش موجود حالياً في الكتالوج بتاعنا بشكل مباشر. 🙏

لكن لو مهتم بالمجال ده، ممكن تبدأ بأساسيات مرتبطة عندنا:
• **{alternatives[0]}** - أساسيات هتفيدك
• **{alternatives[1]}** - مهارات داعمة

تحب أعرض لك كورسات من أي قسم فيهم؟
"""
        else:
            answer = f"""
Sorry, **{topic}** is not currently available in our direct catalog. 🙏

However, you can start with these related foundations:
• **{alternatives[0]}** - Essential basics
• **{alternatives[1]}** - Supporting skills

Would you like to see courses from either of these sections?
"""
            
        return answer, [], [], [], None, None, [], None, None, None, "SAFE_FALLBACK", None

    def _fallback_projects(self, topic: str, is_soft_skills: bool = False) -> List[ProjectDetail]:
        """Generate template projects or practice tasks if LLM fails."""
        topic_lower = topic.lower()
        
        if "sales" in topic_lower or "مبيعات" in topic_lower:
             return [
                ProjectDetail(title="Sales Pipeline Development", difficulty="Intermediate", description="Design a complete sales funnel and stages.", deliverables=["Pipeline Doc", "CRM Field Map"], suggested_tools=["CRM", "Excel"]),
                ProjectDetail(title="Mock Discovery Call", difficulty="Beginner", description="Roleplay a discovery call with a prospect.", deliverables=["Call Script", "Objection Handling Sheet"], suggested_tools=["Zoom/Voice"]),
                ProjectDetail(title="Q4 Forecast Model", difficulty="Advanced", description="Build a revenue forecast model for the team.", deliverables=["Forecast Sheet", "Sensitivity Analysis"], suggested_tools=["Excel", "PowerBI"])
            ]

        if any(x in topic_lower for x in ["data", "analysis", "sql", "excel", "داتا", "تحليل", "بيانات"]):
             return [
                ProjectDetail(title="Sales Performance Dashboard", difficulty="Intermediate", description="Build an interactive dashboard to track sales KPIs.", deliverables=["Interactive Dashboard", "Data Model"], suggested_tools=["Excel", "PowerBI", "Tableau"]),
                ProjectDetail(title="Customer Churn Analysis", difficulty="Advanced", description="Analyze customer data to identify churn factors.", deliverables=["Analysis Report", "Churn Prediction Model"], suggested_tools=["Python", "SQL", "Pandas"]),
                ProjectDetail(title="Retail Inventory Report", difficulty="Beginner", description="Clean and analyze retail inventory data.", deliverables=["Cleaned Dataset", "Summary Report"], suggested_tools=["Excel", "Spreadsheets"])
             ]

        if is_soft_skills:
             return [
                ProjectDetail(title="Role-Playing Session", difficulty="All Levels", description=f"Practice {topic} scenarios with a peer or mentor.", deliverables=["Session Log", "Feedback Note"], suggested_tools=["Voice Recorder", "Notes"]),
                ProjectDetail(title="Situation Analysis", difficulty="Intermediate", description="Analyze a recent workplace conflict or event.", deliverables=["Analysis Report", "Action Plan"], suggested_tools=["Journal"]),
                ProjectDetail(title="Mock Presentation", difficulty="Advanced", description="Prepare and deliver a 10-min talk.", deliverables=["Slide Deck", "Video Recording"], suggested_tools=["PowerPoint", "Camera"])
            ]
        
        return [
            ProjectDetail(title=f"{topic} Starter", difficulty="Beginner", description="Basic app to practice fundamentals.", deliverables=["Console App"], suggested_tools=["IDE"]),
            ProjectDetail(title=f"{topic} Core App", difficulty="Intermediate", description="CRUD application with database.", deliverables=["Web App", "DB Schema"], suggested_tools=["Framework"]),
            ProjectDetail(title=f"{topic} Pro Suite", difficulty="Advanced", description="Full-scale solution.", deliverables=["Microservices", "CI/CD"], suggested_tools=["Docker"])
        ]

    def _fallback_response(self, courses: List[CourseDetail]):
        titles = "\n".join([f"- {c.title}" for c in courses])
        return f"لقيتلك الكورسات دي:\n{titles}", [], courses, [], None, None, [], None, None, None, "COURSE_SEARCH", None

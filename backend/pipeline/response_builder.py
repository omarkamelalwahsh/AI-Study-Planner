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

RESPONSE_SYSTEM_PROMPT = """SYSTEM: Career Copilot — Production System Prompt (v2.0)

You are "Career Copilot": a bilingual (Arabic/English) career guidance + courses assistant.
Your #1 goal: produce correct intent, correct flow, and stable UI output.
You must be deterministic, consistent, and NEVER hallucinate courses. Only use provided catalog results.

────────────────────────────────────────────────────────────────────────────
0) LANGUAGE LOCK (Mandatory)
────────────────────────────────────────────────────────────────────────────
- If user writes Arabic or Arabizi -> respond in Arabic.
- If user writes English -> respond in English.
- Never switch language unless user switches.

────────────────────────────────────────────────────────────────────────────
1) INTENT RULES
────────────────────────────────────────────────────────────────────────────
You MUST select exactly one intent:
A) COURSE_SEARCH: Recommendations, topic keywords.
B) LEARNING_PATH: Explicit requests for a plan/roadmap.
C) PROJECT_IDEAS: Requests for project ideas.
D) CAREER_GUIDANCE: Career decisions, "how to become X".
E) FOLLOW_UP: "more" / "أظهر المزيد" with previous results.
F) EXPLORATION: Unclear goal, needs 3-question flow.

────────────────────────────────────────────────────────────────────────────
2) FLOW STATE & UI CONTRACT
────────────────────────────────────────────────────────────────────────────
You produce ONLY the "answer" text and "ask" field (for questions).
The backend handles cards for courses, projects, and plans.

- If intent = LEARNING_PATH and missing duration/time -> use "ask" to request them.
- If intent = EXPLORATION -> provide supportive intro and use "ask" for 3 questions max.

STRICT OUTPUT JSON SCHEMA:
{
  "intent": "<ONE_OF_INTENTS>",
  "language": "ar" | "en",
  "answer": "<short natural text>",
  "ask": null | { "question": "...", "choices": ["..."] },
  "learning_plan": null | {
     "duration": "...", "time_per_day": "...",
     "schedule": [ { "day_or_week": "...", "topics": ["..."], "tasks": ["..."], "deliverable": "..." } ]
  },
  "courses": [] | [ { "course_id": "...", "title": "...", "level": "...", "category": "...", "instructor": "...", "why": "..." } ],
  "projects": [] | [ { "title": "...", "level": "...", "features": ["..."], "stack": ["..."], "deliverable": "..." } ],
  "flow_state_updates": { "topic": "...", "track": "...", "duration": "...", "time_per_day": "..." }
}
"""

LEARNING_PATH_SYSTEM_PROMPT = """You are Career Copilot. When intent = LEARNING_PATH:

A) If duration or daily_time is missing:
- Ask exactly: "تحب الخطة لمدة قد إيه؟ (أسبوع/أسبوعين/شهر/شهرين) + وقتك يوميًا قد إيه؟ (ساعة/ساعتين/3+)"
- STOP and return null for learning_plan.

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

        # 7. COURSE SEARCH (Rule 1A, 2-Search)
        # Default flow for search or general queries
        
        # LLM Call for narrative
        courses_data = [
            {"course_id": str(c.course_id), "title": c.title, "instructor": c.instructor, "category": c.category, "level": c.level}
            for c in courses[:10]
        ]
        
        try:
            response = await self.llm.generate_json(
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                prompt=f"User Message: {user_message}\nIntent: {intent.value}\nRetrieved Courses: {json.dumps(courses_data)}",
                temperature=0.3
            )
            
            answer = str(response.get("answer") or "جاهز للمساعدة!")
            f_q = str(response.get("ask", {}).get("question") if response.get("ask") else "")
            
            # Map selected courses (Top 3 rule)
            final_courses = []
            for c_obj in courses[:3]:
                c_copy = copy.deepcopy(c_obj)
                c_copy.why_recommended = "Matched by topic relevance."
                final_courses.append(c_copy)
                
            return answer, [], final_courses, [], None, None, courses, None, "courses_only", f_q, intent.value, None

        except Exception as e:
            logger.error(f"Build failed: {e}")
            return "عذراً، حدث خطأ.", [], [], [], None, None, [], None, "fallback", "", intent.value, None

        except Exception as e:
            logger.error(f"Response building failed: {e}")
            answer = "عذراً، حدث خطأ أثناء إعداد الرد. سأحاول مجدداً." if is_ar else "Sorry, an error occurred. I will try again."
            mode = "fallback"

        return answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard, all_relevant, None, mode, f_q, intent_result.intent.value, state_updates

    def _build_catalog_browsing_response(self, message: str, is_ar: bool) -> tuple:
        """Requirement A: 100% Data-Driven (No LLM). Guided Menu + Grouping."""
        from data_loader import data_loader
        msg = message.lower()
        all_cats = data_loader.get_all_categories()
        
        # 1. Umbrella Mapping
        programming_umbrella = ["Programming", "Web Development", "Mobile Development", "Networking", "Data Security", "Technology Applications"]
        
        if any(kw in msg for kw in ["برمجة", "programming", "developer", "software"]):
             cats = [CategoryDetail(name=c, why="تخصص برمجي متاح") for c in programming_umbrella if c in all_cats]
             answer = "عالم البرمجة واسع! دي التخصصات المتاحة عندنا:" if is_ar else "The programming world is huge! Here are our tracks:"
             f_q = "تحب تركز على Web ولا Mobile ولا Security؟" if is_ar else "Focus on Web, Mobile, or Security?"
             return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING", None

        # 2. "I don't know" - Guided Discovery
        if any(kw in msg for kw in ["مش عارف", "don't know", "معرفش"]):
             top_6 = all_cats[:6] # Deterministic top 6
             cats = [CategoryDetail(name=c, why="مجال مشهور ومنصح به") for c in top_6]
             answer = "ولا يهمك! دي أكتر 6 مجالات مطلوبة عندنا. اختار اللي يشدك أكتر:" if is_ar else "No worries! Here are the top 6 trending tracks. Pick one:"
             f_q = "إيه أكتر مجال مهتم بيه من دول؟" if is_ar else "Which area interests you most?"
             return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING", None

        # 3. Default: Full List
        cats = [CategoryDetail(name=c, why="تصفح القسم") for c in all_cats]
        answer = "دي كل الأقسام المتاحة عندنا. اختار أي واحد وهطلعلك تفاصيله:" if is_ar else "Here are all available categories. Pick one to explore:"
        f_q = "تختار أي قسم؟" if is_ar else "Which category would you like to explore?"
        return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING", None

    def _handle_exploration_flow(self, user_msg: str, context: dict, is_ar: bool) -> tuple:
        """
        State-Aware Exploration Flow Responder (Step-by-step).
        Returns 12-tuple including state_updates.
        """
        exp_state = context.get("exploration", {}) if context else {}
        # Ensure defaults
        if not exp_state: exp_state = {"step": 0, "goal": None, "domain": None, "time": None}
        
        step = exp_state.get("step", 0)
        user = user_msg.lower()
        
        # --- PARSING LOGIC ---
        # Only parse if we are NOT at step 0 (Step 0 is start, no answer yet unless user rushed)
        # Actually, if intent is EXPLORATION, we might be starting. If FOLLOWUP, we have an answer.
        # We'll rely on step count.
        
        # If we are effectively "continuing" (user replied), try to parse based on EXPECTED step
        # Note: 'step' in state is the step we ARE ON (waiting for answer).
        # So if step=0, we asked goal, user replied -> parse goal -> set step=1 -> ask domain.
        
        # Correction: User prompt says "After goal -> step=1". So if step=0, we are looking for goal.
        
        parsed_value = None
        
        if step == 0: # Expecting Goal
            if any(w in user for w in ["شغل", "job", "وظيفه", "new"]): parsed_value = "شغل جديد"
            elif any(w in user for w in ["ترقية", "promo", "senior"]): parsed_value = "ترقية"
            elif any(w in user for w in ["تغيير", "shift", "change", "كارير"]): parsed_value = "تغيير كارير"
            
            if parsed_value:
                exp_state["goal"] = parsed_value
                exp_state["step"] = 1
                
        elif step == 1: # Expecting Domain
            if any(w in user for w in ["بيزنس", "business", "إدارة"]): parsed_value = "بيزنس"
            elif any(w in user for w in ["داتا", "data", "بيانات"]): parsed_value = "داتا"
            elif any(w in user for w in ["برمجة", "تكنولوجيا", "tech", "prog"]): parsed_value = "برمجة"
            elif any(w in user for w in ["ماركتنج", "marketing", "تسويق"]): parsed_value = "ماركتنج"
            
            if parsed_value:
                exp_state["domain"] = parsed_value
                exp_state["step"] = 2
                
        elif step == 2: # Expecting Time
            if any(w in user for w in ["ساعة", "1", "one", "hour"]): parsed_value = "ساعة"
            elif any(w in user for w in ["2", "3", "ساعتين", "hours"]): parsed_value = "2-3 ساعات"
            else: 
                # Fallback for numbers or broad
                parsed_value = "وقت كافي" 
            
            if parsed_value:
                exp_state["time"] = parsed_value
                exp_state["step"] = 3

        # State Updates Wrapper
        state_updates = {
            "active_flow": "EXPLORATION_FLOW",
            "exploration": exp_state
        }

        # --- GENERATION LOGIC (For NEXT Step) ---
        new_step = exp_state["step"]
        msg, f_q = "", ""
        
        if new_step == 0:
            # Asking Goal
            msg = "تمام — خلّينا نحدد ده بسرعة.\n\nهدفك إيه؟\nA) شغل جديد B) ترقية C) تغيير كارير\nرد بحرف الاختيار (A/B/C)."
            f_q = "هدفك إيه؟"
            
        elif new_step == 1:
            # Asking Domain
            msg = f"تمام 👍 {exp_state.get('goal', 'هدفنا واضح')}.\n\nميولك أكتر ناحية إيه؟\nA) بيزنس B) داتا C) برمجة D) ماركتنج\nرد بحرف الاختيار (A/B/C/D)."
            f_q = "ميولك إيه؟"
            
        elif new_step == 2:
            # Asking Time
            msg = f"عظيم، اخترت {exp_state.get('domain', 'المجال')}.\n\nوقتك المتاح للمذاكرة يومياً؟\nA) ساعة واحدة B) 2-3 ساعات\nرد بالاختيار."
            f_q = "وقتك المتاح؟"
            
        elif new_step == 3:
            # Final Recommendation
            domain = exp_state.get('domain', 'المجال ده')
            goal = exp_state.get('goal', 'هدفك')
            rec_map = {
                "بيزنس": "Business Administration",
                "داتا": "Data Analysis",
                "برمجة": "Software Engineering",
                "ماركتنج": "Digital Marketing"
            }
            rec_track = rec_map.get(domain, domain)
            
            msg = (
                f"تمام جداً! بناءً على إن هدفك ({goal}) في ({domain}):\n"
                f"أنصحك تبدأ بمسار **{rec_track}**.\n\n"
                "تحب أطلعلك:\n(A) كورسات مناسبة من الكتالوج؟\n(B) خطة مذاكرة بمدة زمنية؟"
            )
            f_q = "تحب كورسات ولا خطة؟"
            
            # Close flow since we are asking the routing question
            state_updates["active_flow"] = None
            # Store context for next turn (e.g. if they say "Courses", we know the domain)
            state_updates["last_topic"] = rec_track
            state_updates["last_intent"] = "EXPLORATION" # Signal context

        return (msg, [], [], [], None, None, [], None, "exploration_questions", f_q, "EXPLORATION", state_updates)

    async def _build_project_ideas_response(self, user_msg: str, topic: Optional[str], courses: List[CourseDetail], is_ar: bool) -> tuple:
        """Generates project ideas using LLM."""
        
        project_ideas_system_prompt = """SYSTEM: Career Copilot - Project Ideas Responder
...
""" # (Kept simplified in diff for brevity, assume content remains same)
        prompt = f"""User asks for project ideas. Topic: {topic or 'General'}.
        Language: {'Arabic' if is_ar else 'English'}.
        Suggest 2 practical, portfolio-ready projects.
        """
        try:
            raw_json = await self.llm.generate_json(prompt, system_prompt=project_ideas_system_prompt, temperature=0.7)
            projects_data = raw_json.get("generated_projects", [])
            answer = raw_json.get("project_intro", "أكيد، دي شوية أفكار لمشاريع ممكن تنفذها:" if is_ar else "Here are some project ideas:")
            
            # Convert to internal model
            projects = []
            for p in projects_data:
                projects.append(ProjectDetail(
                    title=p.get("title", "Project"),
                    difficulty=p.get("difficulty", "Intermediate"),
                    description=p.get("description", ""),
                    tech_stack=p.get("tech_stack", [])
                ))
            
            f_q = "تحب شرح أكتر لأي مشروع؟" if is_ar else "Want more details on any project?"
            # answer, projects, courses, skill_groups, learning_plan, dashboard, all_rel, browsing, mode, f_q, intent, updates
            return (answer, projects, [], [], None, None, [], None, "projects_only", f_q, "PROJECT_IDEAS", None)
            
        except Exception as e:
            logger.error(f"Project ideas failed: {e}")
            msg = "عذراً، مش قادر أجيب أفكار حالياً." if is_ar else "Sorry, cannot generate projects."
            return (msg, [], [], [], None, None, [], None, "fallback", "", "PROJECT_IDEAS", None)

    async def _build_career_guidance_response(self, user_msg: str, intent_result: IntentResult, courses: List[CourseDetail], is_ar: bool) -> tuple:
        """Generates clear, actionable career advice."""
        
        prompt = f"""User asks for career guidance.
        Message: {user_msg}
        Topic/Role: {intent_result.topic or intent_result.role or 'General'}
        Courses: {[c.title for c in courses[:3]]}
        """
        
        try:
            raw_json = await self.llm.generate_json(prompt, system_prompt=CAREER_GUIDANCE_SYSTEM_PROMPT, temperature=0.7)
            
            intro = raw_json.get("guidance_intro", "أهلًا بك، دي خطوات عملية عشان توصل لهدفك:")
            steps = raw_json.get("steps", [])
            f_q = raw_json.get("followup_question", "تحب تعرف أكتر عن كورس معين؟")
            
            # Format answer with bullets
            formatted_steps = "\n".join([f"- {s}" for s in steps])
            final_answer = f"{intro}\n\n{formatted_steps}"
            
            return tuple([final_answer, [], courses, [], None, None, courses, None, "guidance", f_q, "CAREER_GUIDANCE", None])
            
        except Exception as e:
            logger.error(f"Career guidance failed: {e}")
            msg = "عذراً، مش قادر أقدم نصيحة محددة دلوقتي." if is_ar else "Sorry, cannot provide guidance."
            return tuple([msg, [], [], [], None, None, [], None, "fallback", "", "CAREER_GUIDANCE", None])

    async def _build_learning_path_response(self, user_msg: str, intent_result: IntentResult, courses: List[CourseDetail], is_ar: bool, context: Optional[dict] = None) -> tuple:
        """Generates a structured learning plan with Slot Gate."""
        
        # 1. Resolve Topic (Context Recovery)
        topic = intent_result.topic
        if (not topic or topic.lower() in ["general", "plan", "roadmap", "خطة", "مسار"]) and context:
             topic = context.get("last_topic") or context.get("last_search_topic")
        
        # 2. Slot Gate: Check Duration and Time
        duration_keywords = ["أسبوع", "شهر", "week", "month", "days", "يوم"]
        time_keywords = ["ساعة", "ساعتين", "hour", "minutes", "دقيقة"]
        
        has_duration = any(k in user_msg.lower() for k in duration_keywords) or intent_result.duration
        has_time = any(k in user_msg.lower() for k in time_keywords) or intent_result.daily_time
        
        # Check if we already asked (Requirement D: Default if refused/unclear)
        already_asked = context.get("requested_plan_info") if context else False
        
        if not (has_duration and has_time) and not already_asked:
             # Combined ONE concise question if anything is missing
             if not has_duration and not has_time:
                  f_q = "تحب الخطة لمدة قد إيه؟ (أسبوع/شهر) + وقتك يوميًا قد إيه؟ (ساعة/ساعتين)"
                  msg = "تمام 👌 تحب الخطة لمدة قد إيه؟ (أسبوع / أسبوعين / شهر) + وقتك يوميًا قد إيه؟ (ساعة / ساعتين / 3+)"
             elif not has_duration:
                  f_q = "تحب الخطة لمدة قد إيه؟ (أسبوع/شهر/شهرين)"
                  msg = "تمام، تحب الخطة لمدة قد إيه؟ (أسبوع / شهر / شهرين)"
             else:
                  f_q = "تحب تذاكر كام ساعة يوميًا؟ (ساعة/ساعتين/3+)"
                  msg = "تمام، وقتك يوميًا قد إيه؟ (ساعة / ساعتين / 3+)"
                  
             # Return question and MARK that we asked
             return (msg, [], [], [], None, None, [], None, "exploration_questions", f_q, "LEARNING_PATH", {"requested_plan_info": True})

        # 3. Generate Plan (Defaults if still missing after ask)
        duration = intent_result.duration or "4 weeks" # fallback logic
        if not has_duration and already_asked: duration = "4 weeks" # user refused/vague
        
        daily_time = intent_result.daily_time or "1 hour"
        if not has_time and already_asked: daily_time = "60 minutes"
        

        prompt = f"""User asks for a learning plan.
        Topic: {topic or 'General'}
        Duration: {duration}
        Daily Time: {daily_time}
        Message: {user_msg}
        """
        
        try:
            raw_json = await self.llm.generate_json(prompt, system_prompt=LEARNING_PATH_SYSTEM_PROMPT, temperature=0.7)
            
            plan_raw = raw_json.get("learning_plan", {})
            schedule_raw = plan_raw.get("schedule", [])
            
            # Fallback for empty schedule (V21/V22 Hard Rule)
            if not schedule_raw:
                 logger.warning(f"LLM returned empty schedule for {topic}. Falling back.")
                 schedule_raw = [
                     {"day": 1, "title": "Overview", "topics": [f"Intro to {topic}"], "practice": ["Research basics"], "deliverable": "Summary notes"}
                 ]

            schedule = []
            for item in schedule_raw:
                schedule.append(LearningItem(
                    day=item.get("day"),
                    week=item.get("week"),
                    title=item.get("title", "Day Focus"),
                    topics=item.get("topics", []),
                    practice=item.get("practice", []),
                    deliverable=item.get("deliverable"),
                    goals=item.get("topics", []), # Compat
                    tasks=item.get("practice", [])  # Compat
                ))
            
            final_plan = LearningPlan(
                topic=plan_raw.get("topic", topic or "General"),
                duration=plan_raw.get("duration", duration),
                daily_time=plan_raw.get("daily_time", daily_time),
                schedule=schedule,
                weeks=schedule # Support both keys
            )
            
            answer = raw_json.get("answer", "تمام 👌 دي خطة مفصلة لمذاكرة جافا سكريبت:")
            f_q = "تحب تبدأ في أول يوم؟"
            
            return (answer, [], courses, [], final_plan, None, courses, None, "plan_and_courses", f_q, "LEARNING_PATH", None)

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

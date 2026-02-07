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
    CVDashboard, SkillItem, CatalogBrowsingData, CategoryDetail, SemanticResult,
    ChoiceQuestion
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
  "radar": [
      { "area": "Skills Match", "value": 0 },
      { "area": "Experience", "value": 0 },
      { "area": "Impact", "value": 0 },
      { "area": "ATS Readiness", "value": 0 },
      { "area": "Communication", "value": 0 }
  ],
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

RESPONSE_SYSTEM_PROMPT = """You are "Career Copilot", a production-grade career assistant for Zedny.
Your job is to output a STRICT JSON response used by the frontend UI.
You MUST follow the schema and the routing/UX rules below to prevent broken flows.

────────────────────────────────────────────────────────
A) Language & Tone (HARD)
────────────────────────────────────────────────────────
- Mirror the user language: Arabic user → Arabic output. English user → English output.
- Be concise, structured, friendly-professional.
- Never output filler like: "How can I help?" if the user already expressed a goal or topic.
- Avoid long paragraphs. Use short bullets.

────────────────────────────────────────────────────────
B) HARD ROUTING OVERRIDES (Fix "تايه" + track)
────────────────────────────────────────────────────────
1) If user message includes a clear track/topic (e.g., Marketing, Python, Databases, Data Science, Business, Design) 
   then intent MUST NOT be "ASK_CATEGORY". 
   Instead set intent to:
   - "TRACK_START" if user is "lost/تايه" or beginner,
   - OR "COURSE_SEARCH" if user explicitly asks for courses.

2) If user message includes a career goal/role:
   Examples: "عاوز أبقى مدير عام", "مدير مبيعات", "Sales Manager", "General Manager"
   then intent MUST be "CAREER_GUIDANCE" even if the user didn't ask a question.

3) If the user uploaded a CV (upload endpoint):
   intent MUST be "CV_ANALYSIS" and MUST produce a visible response (never empty).
   Always include a CV summary card + one follow-up question.

────────────────────────────────────────────────────────
C) COURSES: Strict grounding rules (HARD)
────────────────────────────────────────────────────────
- You are NOT allowed to invent courses.
- If courses are provided to you by the system context, use them.
- If the system provides zero courses, you MUST say no matching courses and ask a clarification,
  but also include a safe fallback suggestion (e.g., choose a sub-topic).
- Do not mention external platforms or courses outside the catalog.

────────────────────────────────────────────────────────
D) Fix the "تايه" onboarding behavior (HARD)
────────────────────────────────────────────────────────
When user says "عاوز أبدأ أتعلم <TRACK> وتايه":
- DO NOT ask: "تحب تبدأ في أنهي مجال؟" because the track is already known.
- Provide:
  1) A simple roadmap (3 steps)
  2) ONE question about a sub-track (e.g., Digital Marketing / Social Media / Content)
  3) Optionally top 3 catalog courses if provided

Example Arabic behavior:
- Confirm track in one line
- Roadmap bullets
- One question: "تحب تبدأ Digital Marketing ولا Social Media ولا Content؟"

────────────────────────────────────────────────────────
E) CV Upload UX rules (HARD)
────────────────────────────────────────────────────────
When intent = "CV_ANALYSIS":
- Always produce a visible answer + cards.
- Include:
  1) "cv_summary" card: headline + 3-6 bullets (top skills/roles detected)
  2) If skills_vocab filtering discards many skills, do NOT mention internal filtering.
     Instead output "skills_detected" with what you ARE confident about.
  3) Ask ONE follow-up question about target role to continue the flow.
- If rate-limit/429 occurred (even if retried), keep response short and stable.

────────────────────────────────────────────────────────
F) UI Actions (HARD) — Fix "click course to open details"
────────────────────────────────────────────────────────
The frontend supports UI actions.
When returning courses, ALWAYS attach an action for each course:
- action.type = "OPEN_COURSE_DETAILS"
- action.course_id = "<course_id>"
This enables the UI to open a details modal or fetch /courses/{course_id}.

────────────────────────────────────────────────────────
G) Output JSON Schema (STRICT — no extra keys)
────────────────────────────────────────────────────────
Return ONLY valid JSON, no markdown, no comments:

{
  "intent": "TRACK_START" | "COURSE_SEARCH" | "CAREER_GUIDANCE" | "CV_ANALYSIS" | "GENERAL_QA" | "ERROR",
  "language": "ar" | "en",
  "title": string,
  "answer": string,
  "cards": [
    {
      "type": "roadmap" | "skills" | "courses" | "assessment" | "cv_summary" | "next_steps" | "notes",
      "heading": string,
      "bullets": [string, ...]
    }
  ],
  "courses": [
    {
      "course_id": string,
      "title": string,
      "category": string,
      "level": string,
      "description_short": string,
      "action": { "type": "OPEN_COURSE_DETAILS", "course_id": string }
    }
  ],
  "one_question": {
    "question": string,
    "choices": [string, ...]
  }
}

Rules:
- "answer" must never be empty.
- Always include "one_question" with exactly ONE question for intents:
  TRACK_START, CAREER_GUIDANCE, CV_ANALYSIS
- Cards order for TRACK_START: 
  roadmap → next_steps → assessment
- Cards order for CV_ANALYSIS:
  cv_summary → next_steps → assessment
- Cards order for COURSE_SEARCH:
  courses → next_steps (optional)
- Keep bullets short (<= 12 words).

────────────────────────────────────────────────────────
H) ERROR Handling (HARD)
────────────────────────────────────────────────────────
If something fails or data is missing:
- intent = "ERROR"
- Provide a friendly Arabic/English answer
- Ask ONE question to recover
- Do not crash the JSON format.
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
    ) -> "ChatResponse":
        """
        Main response orchestration (v2: Returns ChatResponse Model).
        """
        from data_loader import data_loader
        from models import ChatResponse
        context = context or {}
        
        # 1. Language Handling
        is_ar_msg = data_loader.is_arabic(user_message)
        res_lang = "ar" if is_ar_msg else (context.get("language") or "en")
        is_ar = res_lang == "ar"
        
        # 2. Intent Resolve
        intent = intent_result.intent
        
        # 3. Special Handlers
        if intent == IntentType.CATALOG_BROWSING:
             return self._build_catalog_browsing_response(user_message, is_ar)

        if intent in [IntentType.EXPLORATION, IntentType.EXPLORATION_FOLLOWUP]:
             return self._handle_exploration_flow(user_message, context, is_ar)

        if intent == IntentType.CV_ANALYSIS:
             return await self._build_cv_dashboard(user_message, skill_result, is_ar)

        # 4. UNIFIED LLM PATH
        
        # NO LOOPING (Rule 3)
        # Check if we are about to ask the same thing twice.
        last_ask = context.get("last_ask")
        
        # Prepare course context for LLM
        courses_data = [
            {"course_id": str(c.course_id), "title": c.title, "instructor": c.instructor, "category": c.category, "level": c.level}
            for c in courses[:5] # Provide a few for context, prompt says Top 3
        ]
        
        slots = intent_result.slots or {}
        duration = slots.get("duration") or getattr(intent_result, "duration", None)
        daily_time = slots.get("daily_time") or getattr(intent_result, "daily_time", None)

        prompt_context = {
            "user_message": user_message,
            "intent": str(intent.value if hasattr(intent, 'value') else intent),
            "session_language": res_lang,
            "retrieved_courses": courses_data,
            "slots": {
                "duration": duration,
                "daily_time": daily_time,
                "topic": slots.get("topic") or intent_result.topic
            },
            "last_ask": last_ask
        }
        
        try:
            response = await self.llm.generate_json(
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                prompt=f"Context: {json.dumps(prompt_context)}",
                temperature=0.0
            )
            
            # --- FIX: Extract variables from LLM response ---
            final_intent = response.get("intent", str(intent.value if hasattr(intent, 'value') else intent))
            title = response.get("title", "")
            answer = response.get("answer", "")
            
            from models import Card, CourseDetail, Action, OneQuestion
            cards_raw = response.get("cards", [])
            cards = [Card(**c) for c in cards_raw if isinstance(c, dict)]
            
            # Match courses with catalog data and attach Action
            courses_raw = response.get("courses", [])
            final_courses = []
            for cr in courses_raw:
                c_id = cr.get("course_id")
                # Look for the full detail in original list
                match = next((c for c in courses if str(c.course_id) == str(c_id)), None)
                if match:
                    match_copy = copy.deepcopy(match)
                    match_copy.description_short = cr.get("description_short", match_copy.description_short)
                    match_copy.action = Action(course_id=str(c_id))
                    final_courses.append(match_copy)

            oq_data = response.get("one_question")
            one_question = OneQuestion(**oq_data) if oq_data and isinstance(oq_data, dict) else None
            
            state_updates = response.get("flow_state_updates", {})

            # Build final Response Object
            from models import ChatResponse, FlowStateUpdates
            return ChatResponse(
                intent=final_intent,
                language=res_lang,
                title=title,
                answer=answer,
                cards=cards,
                courses=final_courses,
                one_question=one_question,
                flow_state_updates=FlowStateUpdates(**state_updates) if state_updates else None
            )

        except Exception as e:
            logger.error(f"Unified build v2 failed: {e}")
            from models import ChatResponse, OneQuestion
            fallback_msg = "تمام، تحب تبدأ بأنهي مجال من دول؟" if is_ar else "Great, which of these domains would you like to start with?"
            choices = ["Programming", "Data Science", "Marketing", "Business", "Design"]
            one_question = OneQuestion(question=fallback_msg, choices=choices)
            return ChatResponse(
                intent="ERROR",
                language=res_lang,
                title="Error",
                answer=fallback_msg,
                one_question=one_question
            )

        except Exception as e:
            logger.error(f"Unified build v1.0 failed: {e}")
            fallback_msg = "تمام، تحب تبدأ بأنهي مجال من دول؟" if is_ar else "Great, which of these domains would you like to start with?"
            choices = ["Programming", "Data Science", "Marketing", "Business", "Design"]
            from models import OneQuestion
            one_question = OneQuestion(question=fallback_msg, choices=choices)
            return fallback_msg, "Error", [], [], one_question, IntentType.ERROR, {"language": res_lang}

    def _handle_exploration_flow(self, user_msg: str, context: dict, is_ar: bool) -> tuple:
        """
        Zedny Exploration Flow (Simplified v1.0).
        1) Detect Goal/Job -> Domains.
        2) Unsure at domain step -> Repeat once.
        3) Domain picked -> Switch to COURSE_SEARCH (skip sub-tracks).
        """
        exp_state = context.get("exploration", {})
        if not exp_state: exp_state = {"step": 1, "unsure_count": 0}
        
        step = exp_state.get("step", 1)
        user = user_msg.lower()
    def _handle_exploration_flow(self, user_msg: str, context: dict, is_ar: bool) -> "ChatResponse":
        """Deterministic Exploration Flow v2 (Aligne with Schema)."""
        from models import ChatResponse, OneQuestion, Card, FlowStateUpdates
        exp_state = context.get("exploration", {})
        step = exp_state.get("step", 1)
        main_domains = ["Programming", "Data Science", "Marketing", "Business", "Design"]
        
        if step == 1:
            q = "تمام 👌 اختار مجال من دول عشان أساعدك تبدأ بسرعة:" if is_ar else "Great! Pick a domain to get started quickly:"
            oq = OneQuestion(question=q, choices=main_domains)
            exp_state["step"] = 2
            return ChatResponse(
                intent="EXPLORATION", language="ar" if is_ar else "en",
                title="Exploration", answer=q, one_question=oq,
                flow_state_updates=FlowStateUpdates(exploration=exp_state)
            )
        
        # ... simple transition or fallback
        ans = "تحب تبدأ في أنهي مجال من دول؟" if is_ar else "Which field would you like to start with?"
        return ChatResponse(
            intent="EXPLORATION", language="ar" if is_ar else "en",
            title="Exploration", answer=ans, 
            one_question=OneQuestion(question=ans, choices=main_domains)
        )

    def _build_catalog_browsing_response(self, user_msg: str, is_ar: bool) -> "ChatResponse":
        """Rule C: Return ONLY choices."""
        from models import ChatResponse, OneQuestion
        main_domains = ["Programming", "Data Science", "Marketing", "Business", "Design"]
        q = "دي المجالات المتاحة عندنا، تحب تستكشف إيه؟" if is_ar else "These are our domains, what would you like to explore?"
        return ChatResponse(
            intent="CATALOG_BROWSING", language="ar" if is_ar else "en",
            title="Browse Catalog", answer=q,
            one_question=OneQuestion(question=q, choices=main_domains)
        )


    async def _build_cv_dashboard(self, user_message: str, skill_result: SkillValidationResult, is_ar: bool) -> tuple:
        """Generate structured CV Dashboard + Strict Schema Response."""
        # This will follow the NEW schema but also include the dashboard data for the rich UI
        prompt = f"""User CV Analysis Request:
{user_message[:6000]}

Validated Skills: {', '.join(skill_result.validated_skills)}
"""
        try:
            # We use the main RESPONSE_SYSTEM_PROMPT so it follows Rule E (visible response + cards)
            response = await self.llm.generate_json(
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                prompt=f"Task: Analyze CV. Context: {prompt}",
                temperature=0.2
            )
            
            answer = str(response.get("answer") or "")
            title = str(response.get("title") or "CV Analysis")
            
            from models import Card
            cards_raw = response.get("cards", [])
            cards = [Card(**c) for c in cards_raw if isinstance(c, dict)]
            
            from models import OneQuestion
            oq_data = response.get("one_question")
            one_question = OneQuestion(**oq_data) if oq_data and isinstance(oq_data, dict) else None

            # Generate the Dashboard Data (Rich UI)
            # We can use a simpler call for the dashboard numeric data
            dash_prompt = f"From this CV, generate strictly numeric metrics for score, skills, radar, and atsChecklist for a dashboard. CV: {user_message[:2000]}"
            dash_res = await self.llm.generate_json(
                system_prompt=CV_ANALYSIS_SYSTEM_PROMPT,
                prompt=dash_prompt,
                temperature=0.0
            )

            from models import CVDashboard, RadarItem, Action
            dashboard_data = CVDashboard(
                candidate=dash_res.get("candidate", {}),
                score=dash_res.get("score", {}),
                roleFit=dash_res.get("roleFit", {}),
                skills=dash_res.get("skills", {"strong": [], "weak": [], "missing": []}),
                radar=[RadarItem(**r) for r in dash_res.get("radar", [])],
                projects=dash_res.get("projects", []),
                atsChecklist=dash_res.get("atsChecklist", []),
                notes=dash_res.get("notes", {}),
                recommendations=dash_res.get("recommendations", [])
            )

            # Map dashboard projects to main ChatResponse projects for UI
            from models import ProjectDetail
            final_projects = []
            portfolio_actions = dash_res.get("portfolio_actions", [])
            for pa in portfolio_actions:
                 final_projects.append(ProjectDetail(
                     title=pa.get("title", "Project"),
                     level=pa.get("level", "Advanced"),
                     description=pa.get("description", ""),
                     features=pa.get("skills_targeted", []),
                     stack=pa.get("deliverables", []),
                     deliverable="Complete Project"
                 ))

            # Return in the unified format
            from models import ChatResponse, FlowStateUpdates
            return ChatResponse(
                intent="CV_ANALYSIS",
                language="ar" if is_ar else "en",
                title=title,
                answer=answer,
                cards=cards,
                one_question=one_question,
                dashboard=dashboard_data,
                radar=dashboard_data.radar,
                projects=final_projects,
                flow_state_updates=FlowStateUpdates(dashboard=dashboard_data.model_dump())
            )

        except Exception as e:
            logger.error(f"CV Analysis built with schema failed: {e}")
            from models import ChatResponse
            err_msg = "حدث خطأ أثناء تحليل السيرة الذاتية." if is_ar else "Error analyzing CV."
            return ChatResponse(intent="ERROR", language="ar" if is_ar else "en", title="Error", answer=err_msg)

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

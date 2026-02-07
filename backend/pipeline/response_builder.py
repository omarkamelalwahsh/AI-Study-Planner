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

RESPONSE_SYSTEM_PROMPT = """SYSTEM: Career Copilot Advisor (PRODUCTION v3)
Return only valid JSON matching this schema:
{
  "success": true,
  "intent": "COURSE_SEARCH|CAREER_GUIDANCE|GENERAL_QA|FOLLOW_UP|SAFE_FALLBACK",
  "message": "your advice or question here",
  "courses": [{"course_id": "...", "description_short": "..."}],
  "categories": ["cat1", "cat2"],
  "errors": []
}

RULES:
1) Use user's language (Arabic or English).
2) Grounding: Only recommend provided courses.
3) No extra fields (radar, cards, etc) unless specifically needed for complex paths.
4) Response must be valid JSON only."""

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
        
        # 3. Special Handlers (Minimal)
        if intent == IntentType.CATALOG_BROWSE:
             # Standard fallback categories
             cats = ["Programming", "Data Science", "Marketing", "Business", "Design"]
             msg = "هذه هي المجالات المتاحة عندنا، تحب تستكشف إيه؟" if is_ar else "These are our domains, what would you like to explore?"
             return ChatResponse(
                success=True, intent=IntentType.CATALOG_BROWSE, message=msg, categories=cats, language=res_lang
             )

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
                temperature=0.0,
                max_tokens=2048
            )
            
            # --- FINAL SCHEMA COMPLIANCE (STRICT) ---
            final_intent = response.get("intent") or str(intent.value if hasattr(intent, 'value') else intent)
            message = response.get("message") or response.get("answer") or ""
            success = response.get("success", True)
            
            from models import Card, CourseDetail, Action, OneQuestion, QuizData, RadarItem
            cards_raw = response.get("cards", [])
            cards = [Card(**c) for c in cards_raw if isinstance(c, dict)]
            
            # Radar: FORCE LIST
            radar_raw = response.get("radar", [])
            if isinstance(radar_raw, dict):
                 radar_raw = [{"area": k, "value": v} for k, v in radar_raw.items()]
            final_radar = [RadarItem(**r) for r in radar_raw if isinstance(r, dict)]

            # Quiz: Initialize or map
            quiz_raw = response.get("quiz", {})
            quiz_data = QuizData(**quiz_raw) if quiz_raw else QuizData()
            
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
            return ChatResponse(
                success=success,
                intent=final_intent,
                message=message,
                courses=final_courses,
                categories=response.get("categories", []),
                errors=response.get("errors", []),
                next_action=response.get("next_action"),
                language=res_lang,
                cards=cards,
                radar=final_radar,
                quiz=quiz_data,
                flow_state_updates=FlowStateUpdates(**state_updates) if state_updates else None,
                meta={"flow": "production_v3_core"}
            )

        except Exception as e:
            logger.error(f"Production build failed: {e}", exc_info=True)
            from models import ChatResponse
            return ChatResponse(
                success=False,
                intent=IntentType.SAFE_FALLBACK,
                message="عذراً، حدث خطأ في النظام. هل يمكنني مساعدتك؟" if is_ar else "Sorry, a system error occurred. Can I help you?",
                categories=["Programming", "Marketing", "Data Science"],
                errors=[str(e)]
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
            
            from models import OneQuestion, QuizData
            oq_data = response.get("one_question")
            one_question = OneQuestion(**oq_data) if oq_data and isinstance(oq_data, dict) else None
            
            # Quiz is empty for CV
            quiz_data = QuizData()

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
                quiz=quiz_data,
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

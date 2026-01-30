"""
Career Copilot RAG Backend - Step 6: Response Builder
Dynamic response generation based on intent type.
"""
import logging
from typing import List, Optional, Dict

from llm.base import LLMBase
from models import (
    IntentType, IntentResult, CourseDetail, ProjectDetail, 
    SkillValidationResult, SkillGroup, LearningPlan, WeeklySchedule, LearningPhase,
    CVDashboard
)

logger = logging.getLogger(__name__)


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

RESPONSE_SYSTEM_PROMPT = """SYSTEM: You are Career Copilot's Career Guidance Planner.
You create a role-aligned plan and required skills, and you request catalog course mapping.
You MUST remain strictly relevant to the selected track and role.

CRITICAL:
- Output ONLY valid JSON.
- Do NOT invent course titles. You only output "skill_groups" (which imply needs). The backend maps them.
- Do NOT include unrelated domains (e.g., Agile, Project Management, Supply Chain) unless the user explicitly asked.

INPUTS:
- user_query
- skills_catalog (available categories)

UNIVERSAL OUTPUT POLICY:
- Always return:
  1) skill_groups (core + supporting)
  2) learning_plan (phases)
  3) courses (selection from retrieval)
  4) projects (role-appropriate)

ROLE CONSTRAINTS (Apply if Role Detected):
- IF Role="Sales Manager":
  Core skills: Sales process, Funnel, CRM, Negotiation, Forecasting, Coaching.
  Deliverables: ICP, Pipeline stages, Weekly forecast template, Win/loss review, Coaching plan.
  FORBIDDEN: Agile, Supply Chain, Deep Learning, Churn Modeling (unless asked).
  Projects: Roleplays, CRM setup, Plan creation.

- IF Role="Data Analyst":
  Core skills: Excel, SQL, Stats, Viz.
  Deliverables: KPI Dashboard, Analysis Report.

OUTPUT FORMAT (JSON ONLY):
{
  "answer": "Helpful overview...",
  "skill_groups": [
    { "skill_area": "Sales Strategy", "why_it_matters": "...", "skills": ["..."] }
  ],
  "learning_plan": {
    "phases": [
       { "title": "Phase 1: ...", "weeks": "...", "skills": ["..."], "deliverables": ["..."] }
    ]
  },
  "courses": [],
  "projects": [
    { "title": "...", "difficulty": "...", "description": "...", "deliverables": ["..."], "suggested_tools": ["..."] }
  ]
}
"""


class ResponseBuilder:
    """
    Step 6: Build dynamic response based on intent.
    """
    
    def __init__(self, llm: LLMBase):
        self.llm = llm
    
    async def build(
        self,
        intent_result: IntentResult,
        courses: List[CourseDetail],
        skill_result: SkillValidationResult,
        user_message: str,
        context: Optional[dict] = None,
    ) -> tuple[str, List[ProjectDetail], List[CourseDetail], List[SkillGroup], Optional[LearningPlan], Optional[CVDashboard]]:
        """
        Build the final response based on intent.
        """
        # Route strict CV Analysis
        if intent_result.intent == IntentType.CV_ANALYSIS:
             # Check if we have actual content to analyze
             # If validated skills are empty and message is short (just the command "Evaluate"), ask for CV
             is_command_only = len(user_message.split()) < 5
             if not skill_result.validated_skills and is_command_only:
                 answer = "أهلاً بك! لتقييم سيرتك الذاتية، يرجى رفع ملف الـ CV أولاً أو نسخ النص هنا. 📄"
                 return answer, [], [], [], None, None
                 
             answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard = await self._build_cv_dashboard(user_message, skill_result)
        else:
            # Apply strict display limit of 5 (V6 Pagination Patch)
            num_courses = len(courses)
            k_return = min(5, num_courses)
            courses_context = courses[:k_return]
            
            # Initialize return variables for scope safety
            answer = ""
            projects = []
            final_courses = []
            skill_groups = []
            learning_plan = None
            cv_dashboard = None
            
            # Prepare context for the LLM
            courses_data = [
                {
                    "course_id": c.course_id,
                    "title": c.title,
                    "level": c.level,
                    "category": c.category,
                    "instructor": c.instructor,
                    "duration_hours": c.duration_hours,
                    "description": c.description,
                }
                for c in courses_context
            ]
            
            skills_data = {
                "validated": skill_result.validated_skills,
                "unmatched": skill_result.unmatched_terms,
                "skill_to_domain": skill_result.skill_to_domain
            }
            
            session_state = {}
            if context:
                session_state = {
                    "last_intent": context.get("last_intent"),
                    "last_topic": context.get("last_topic"),
                    "last_domain": context.get("last_domain"),
                    "last_results_course_ids": context.get("last_results_course_ids", []),
                    "last_plan_constraints": context.get("last_plan_constraints"),
                    "pagination_offset": context.get("pagination_offset", 0),
                    "plan_asked": context.get("plan_asked", False), # V6: Prevent repeated plan questions
                    "brief_explanation": context.get("brief_explanation") # V5: Get explanation from context
                }

            prompt = f"""User Message: "{user_message}"
Intent identified: {intent_result.intent.value}
Target Role: {intent_result.role}

RETRIEVED DATA (Only use this):
catalog_results: {courses_data}
skills_catalog: {skills_data}
session_state: {session_state}

Generate the structured response in JSON format according to the rules."""

            try:
                response = await self.llm.generate_json(
                    prompt=prompt,
                    system_prompt=RESPONSE_SYSTEM_PROMPT,
                    temperature=0.3
                )
                
                # 1. Answer & Clarification
                answer = response.get("answer", "")
                if response.get("clarifying_question"):
                    answer = f"{answer}\n\n{response['clarifying_question']}"
                    
                # 2. Skill Groups
                for sg in response.get("skill_groups", []):
                    skill_groups.append(SkillGroup(
                        skill_area=sg.get("skill_area", ""),
                        why_it_matters=sg.get("why_it_matters", ""),
                        skills=sg.get("skills", [])
                    ))

                # 3. Projects (Robust Fallback logic handled by prompt instructions, but kept safe here)
                for p in response.get("projects", []):
                    projects.append(ProjectDetail(
                        title=p.get("title", "Project"),
                        difficulty=p.get("difficulty", "Beginner"),
                        description=p.get("description", ""),
                        deliverables=p.get("deliverables", []),
                        suggested_tools=p.get("suggested_tools", []),
                        # V4 Migration Fix: Populate legacy fields to prevent Frontend Crash
                        level=p.get("difficulty", "Beginner"), 
                        skills=p.get("suggested_tools", []) # Map tools to skills for display
                    ))
                if intent_result.intent == IntentType.PROJECT_IDEAS and not projects:
                    # Minimal fallback if LLM returns nothing involved
                    projects = self._fallback_projects(intent_result.role or "General")

                # 4. Learning Plan
                lp_data = response.get("learning_plan")
                if lp_data:
                    schedule = []
                    phases = []
                    
                    # Legacy Schedule
                    for week in lp_data.get("schedule", []):
                        schedule.append(WeeklySchedule(
                            week=week.get("week", 1),
                            focus=week.get("focus", ""),
                            courses=week.get("courses", []),
                            outcomes=week.get("outcomes", [])
                        ))
                    
                    # V6 Phases
                    for ph in lp_data.get("phases", []):
                         phases.append(LearningPhase(
                             title=ph.get("title", ""),
                             weeks=ph.get("weeks", ""),
                             skills=ph.get("skills", []),
                             deliverables=ph.get("deliverables", [])
                         ))

                    learning_plan = LearningPlan(
                        weeks=lp_data.get("weeks"),
                        hours_per_day=lp_data.get("hours_per_day"),
                        schedule=schedule,
                        phases=phases
                    )
                    
                # 5. Course Processing (Selection + Truncation)
                selected_course_ids = set()
                llm_courses = response.get("courses", [])
                
                # Map LLM enriched fields (reason, short desc) back to objects
                enriched_courses_map = {}
                for c in llm_courses:
                    cid = c.get("course_id")
                    if cid: 
                        selected_course_ids.add(cid)
                        enriched_courses_map[cid] = c

                if learning_plan:
                    for week in learning_plan.schedule:
                        for cid in week.courses: selected_course_ids.add(cid)

                # Filter & Enrich original course objects
                
                # CRITICAL V5 FIX: If LLM returns an empty course list, respect it.
                # Do NOT fallback to courses_context unless the intent EXPLICITLY requires them (like COURSE_SEARCH)
                # and the LLM failed to specify which ones.
                
                if selected_course_ids:
                    for course in (courses_context if courses_context else courses):
                        if course.course_id in selected_course_ids:
                            new_course = course.model_copy()
                            enrich_data = enriched_courses_map.get(course.course_id, {})
                            
                            full_desc = enrich_data.get("description_full") or course.description or ""
                            short_desc = enrich_data.get("description_short") or (full_desc[:180] + "..." if len(full_desc) > 180 else full_desc)
                            
                            new_course.description_full = full_desc
                            new_course.description_short = short_desc
                            new_course.description = short_desc
                            new_course.reason = enrich_data.get("reason")
                            new_course.cover = enrich_data.get("cover")
                            final_courses.append(new_course)
                elif intent_result.intent in [IntentType.COURSE_SEARCH, IntentType.CATALOG_BROWSING, IntentType.CAREER_GUIDANCE]:
                    # Fallback for search and guidance intents if LLM forgot to pick specific course_ids
                    for course in (courses_context[:5] if courses_context else courses[:5]):
                        new_course = course.model_copy()
                        new_course.description = (course.description[:180] + "...") if course.description and len(course.description) > 180 else course.description
                        new_course.reason = "مرشح بناءً على تخصصك المختار."
                        final_courses.append(new_course)
                
                # CRITICAL V6 Safe Guard: If COURSE_SEARCH and still no courses, force fallback
                if intent_result.intent == IntentType.COURSE_SEARCH and not final_courses:
                    answer, projects, final_courses, skill_groups, learning_plan = self._fallback_response(courses_context[:5] if courses_context else courses[:5])

                # CRITICAL V7 FIX: LEARNING_PATH Contract Enforcement
                # Always ensure courses and projects/practice tasks are present for Learning Paths
                if intent_result.intent == IntentType.LEARNING_PATH:
                    # 1. Ensure at least 6 Courses (fill up if LLM provided fewer)
                    if len(final_courses) < 6:
                        logger.info(f"Enforcing Courses for Learning Path (Current: {len(final_courses)}, Needs: 6)")
                        candidates = courses_context if courses_context else courses
                        existing_ids = {c.course_id for c in final_courses}
                        
                        for c in candidates:
                            if len(final_courses) >= 6: break
                            if c.course_id not in existing_ids:
                                new_c = c.model_copy()
                                new_c.reason = "إضافي لإكمال مسار التعلم الشامل."
                                final_courses.append(new_c)
                                existing_ids.add(c.course_id)

                    # 2. Ensure Projects / Practice Tasks
                    if not projects:
                         logger.info("Enforcing Projects/Tasks for Learning Path")
                         is_soft_skills = any("soft" in sg.skill_area.lower() for sg in skill_groups) or "واصل" in user_message or "soft" in user_message.lower()
                         projects = self._fallback_projects(intent_result.role or "General", is_soft_skills=is_soft_skills)
                    
                    # 3. Ensure Learning Plan (Phases) - Force 3 phases if less or missing
                    if not learning_plan or len(learning_plan.phases) < 3:
                         logger.info("Enforcing Complete Phased Plan (3 Phases Minimum)")
                         learning_plan = LearningPlan(
                             weeks=12,
                             hours_per_day=2.0,
                             phases=[
                                 LearningPhase(title="المرحلة الأولى: التأسيس والوعي الذاتي", weeks="1-4", skills=["الأساسيات والمفاهيم"], deliverables=["تقييم أولي للمهارات"]),
                                 LearningPhase(title="المرحلة الثانية: الممارسة والتطبيق", weeks="5-8", skills=["الأدوات المتقدمة"], deliverables=["تطبيق عملي صغير"]),
                                 LearningPhase(title="المرحلة الثالثة: الإتقان والتخصص", weeks="9-12", skills=["معايير الاحتراف"], deliverables=["مشروع تخرج متكامل"])
                             ]
                         )

                    # 4. Mandatory Personalization Follow-up
                    # If the LLM didn't provide a clarifying_question, add a specific specialization question
                    if not response.get("clarifying_question"):
                         followup = "عشان أخصص الخطة دي ليك أكتر، هل حابب تتخصص في مجال معين داخل التخصص ده؟ (مثلاً: Finance, Healthcare, Retail?)"
                         answer = f"{answer}\n\n{followup}"

                # CRITICAL V6 FIX: Ensure projects are present for Guidance and Projects intents (Legacy check)
                if intent_result.intent in [IntentType.PROJECT_IDEAS, IntentType.CAREER_GUIDANCE] and not projects:
                    projects = self._fallback_projects(intent_result.role or "General")

            except Exception as e:
                logger.error(f"Response building failed: {e}")
                if not courses:
                    answer = "للأسف مش لاقي كورسات مناسبة حالياً. ممكن توضحلي أكتر؟"
                else:
                    answer, projects, final_courses, skill_groups, learning_plan = self._fallback_response(courses[:5])
        
        # At the end, return all collected variables
        return answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard

    async def _build_cv_dashboard(self, user_message: str, skill_result: SkillValidationResult) -> tuple:
        """Generate structured CV Dashboard with Rich UI Schema."""
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
            # Note: We pass primitive dicts directly because Pydantic models (CVDashboard) 
            # defined in models.py now support these dict structures.
            dashboard_data = CVDashboard(
                candidate=response.get("candidate", {}),
                score=response.get("score", {}),
                roleFit=response.get("roleFit", {}),
                skills=response.get("skills", {"strong": [], "weak": [], "missing": []}),
                radar=response.get("radar", []),
                projects=response.get("projects", []),
                atsChecklist=response.get("atsChecklist", []),
                notes=response.get("notes", {}),
                # Legacy fallback field
                recommendations=[str(p.get('title', 'Project')) for p in response.get("projects", [])]
            )

            # Standard Chat Response
            answer = f"🔍 **Analysis Complete for {dashboard_data.candidate.get('targetRole', 'your role')}**\n\n" \
                     f"**Score:** {dashboard_data.score.get('overall', 0)}/100\n" \
                     f"**Summary:** {dashboard_data.roleFit.get('summary', '')}\n\n" \
                     f"Check the Dashboard below for a deep dive into your skills and gaps! ⬇️"
            
            # CRITICAL User Fix: Fix tokenization of keywords
            missing = dashboard_data.skills.missing
            clean_missing = []
            for m in missing:
                 if isinstance(m, dict):
                      name = m.get("name", "")
                      # Split camelCase or distinct words if stuck together
                      import re
                      # Basic split by capital letter if length is suspicious
                      if len(name) > 15 and " " not in name: 
                           name = " ".join(re.findall('[A-Z][^A-Z]*', name))
                      m["name"] = name
                      clean_missing.append(m)
                 else:
                      clean_missing.append(m)
            dashboard_data.skills.missing = clean_missing

            # CRITICAL User Fix: Fetch Courses for "course_needs" from Catalog
            # Even if score is high, we must show growth courses.
            course_needs = response.get("course_needs", [])
            final_courses = []
            from data_loader import data_loader
            
            for need in course_needs:
                 topic = need.get("topic", "")
                 # Search catalog
                 results = data_loader.search_courses_by_title(topic)
                 if not results:
                      # Try category or skill lookup
                      skill_info = data_loader.get_skill_info(topic)
                      if skill_info:
                           results = data_loader.get_courses_for_skill(skill_info.get("skill_norm", ""))
                 
                 # Add top 2 results
                 for c_dict in results[:2]:
                      c_obj = CourseDetail(**c_dict)
                      c_obj.reason = f"{need.get('type', 'Growth').title()}: {need.get('rationale', 'Recommended for you.')}"
                      if c_obj.course_id not in [x.course_id for x in final_courses]:
                           final_courses.append(c_obj)

            # Map Portfolio Actions to Projects
            projects = []
            for act in response.get("portfolio_actions", []):
                 projects.append(ProjectDetail(
                      title=act.get("title", "Project"),
                      difficulty=act.get("level", "Intermediate"),
                      description=act.get("description", ""),
                      deliverables=act.get("deliverables", []),
                      suggested_tools=act.get("skills_targeted", [])
                 ))
            
            # Map Recommendations strictly
            dashboard_data.recommendations = response.get("recommendations", [])

            return answer, projects, final_courses, [], None, dashboard_data

        except Exception as e:
            logger.error(f"CV Dashboard generation failed: {e}")
            return "Analysis failed. Please try again.", [], [], [], None, None

    async def build_fallback(
        self,
        user_message: str,
        topic: str
    ) -> tuple[str, List[ProjectDetail], List[CourseDetail], List[SkillGroup], Optional[LearningPlan]]:
        """
        Generate a smart fallback response for out-of-scope topics.
        """
        prompt = f"""User asked about: "{user_message}"
Topic identified: "{topic}" (Not found in catalog)

Task:
1. Briefly define what {topic} is (1 sentence).
2. Apologize clearly that it is not currently in our catalog.
3. Suggest 2-3 alternative related domains we MIGHT have (from: Technology, Business, Design, Soft Skills).
4. Do NOT invent specific courses.

Output JSON:
{{
  "answer": "smart fallback text",
  "skill_groups": [],
  "courses": [],
  "projects": [],
  "learning_plan": null
}}
"""
        try:
            response = await self.llm.generate_json(
                prompt=prompt,
                system_prompt="You are a helpful assistant handling out-of-scope queries.",
                temperature=0.3
            )
            return response.get("answer", "عذراً، هذا المجال غير متوفر حالياً."), [], [], [], None
        except Exception:
             return "عذراً، هذا الموضوع غير متوفر في الكتالوج حالياً.", [], [], [], None

    def _fallback_projects(self, topic: str, is_soft_skills: bool = False) -> List[ProjectDetail]:
        """Generate template projects or practice tasks if LLM fails."""
        topic_lower = topic.lower()
        
        # Guardrail: Sales Manager Projects
        if "sales" in topic_lower or "مبيعات" in topic_lower:
             return [
                ProjectDetail(title="Sales Pipeline Development", difficulty="Intermediate", description="Design a complete sales funnel and stages.", deliverables=["Pipeline Doc", "CRM Field Map"], suggested_tools=["CRM", "Excel"], level="Intermediate", skills=["Sales Strategy"]),
                ProjectDetail(title="Mock Discovery Call", difficulty="Beginner", description="Roleplay a discovery call with a prospect.", deliverables=["Call Script", "Objection Handling Sheet"], suggested_tools=["Zoom/Voice"], level="Beginner", skills=["Communication"]),
                ProjectDetail(title="Q4 Forecast Model", difficulty="Advanced", description="Build a revenue forecast model for the team.", deliverables=["Forecast Sheet", "Sensitivity Analysis"], suggested_tools=["Excel", "PowerBI"], level="Advanced", skills=["Forecasting"])
            ]

        if is_soft_skills:
             return [
                ProjectDetail(title="Role-Playing Session", difficulty="All Levels", description=f"Practice {topic} scenarios with a peer or mentor.", deliverables=["Session Log", "Feedback Note"], suggested_tools=["Voice Recorder", "Notes"], level="All Levels", skills=[topic, "Communication"]),
                ProjectDetail(title="Situation Analysis", difficulty="Intermediate", description="Analyze a recent workplace conflict or event.", deliverables=["Analysis Report", "Action Plan"], suggested_tools=["Journal"], level="Intermediate", skills=[topic, "Critical Thinking"]),
                ProjectDetail(title="Mock Presentation", difficulty="Advanced", description="Prepare and deliver a 10-min talk.", deliverables=["Slide Deck", "Video Recording"], suggested_tools=["PowerPoint", "Camera"], level="Advanced", skills=[topic, "Public Speaking"])
            ]
        
        return [
            ProjectDetail(title=f"{topic} Starter", difficulty="Beginner", description="Basic app to practice fundamentals.", deliverables=["Console App"], suggested_tools=["IDE"], level="Beginner", skills=["IDE"]),
            ProjectDetail(title=f"{topic} Core App", difficulty="Intermediate", description="CRUD application with database.", deliverables=["Web App", "DB Schema"], suggested_tools=["Framework"], level="Intermediate", skills=["Framework"]),
            ProjectDetail(title=f"{topic} Pro Suite", difficulty="Advanced", description="Full-scale solution.", deliverables=["Microservices", "CI/CD"], suggested_tools=["Docker"], level="Advanced", skills=["Docker"])
        ]

    def _fallback_response(self, courses: List[CourseDetail]):
        titles = "\n".join([f"- {c.title}" for c in courses])
        return f"لقيتلك الكورسات دي:\n{titles}", [], courses, [], None

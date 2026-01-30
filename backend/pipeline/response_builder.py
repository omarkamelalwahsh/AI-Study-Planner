"""
Career Copilot RAG Backend - Step 6: Response Builder
Dynamic response generation based on intent type.
"""
import logging
from typing import List, Optional, Dict
import copy

from llm.base import LLMBase
from models import (
    IntentType, IntentResult, CourseDetail, ProjectDetail, 
    SkillValidationResult, SkillGroup, LearningPlan, WeeklySchedule, LearningPhase,
    CVDashboard, SkillItem
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

RESPONSE_SYSTEM_PROMPT = """SYSTEM: You are "Career Copilot" — a career guidance + internal-catalog course recommender.
Your #1 priority is CORRECTNESS and TRACEABILITY over verbosity.

You must handle ANY user question (Arabic/English/mixed, typos included) without hallucinating, without crashing,
and without producing irrelevant recommendations.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A) NON-NEGOTIABLE CONSTRAINTS (HARD RULES)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1) Catalog-Only (NO HALLUCINATION):
- You MUST recommend ONLY from retrieved_catalog_courses provided by the backend.
- You MUST NOT invent course titles, IDs, instructors, categories, levels, or descriptions.
- If retrieved_catalog_courses is empty OR none are relevant, recommended_courses MUST be [].

2) Precision-First:
- It is better to return 1–3 correct courses than many mixed courses.
- Never include unrelated “General” courses just to increase count.

3) No Automatic Plan / No Automatic Projects:
- DO NOT generate a learning plan (phases/weeks/timeline/roadmap/deliverables) unless the user explicitly asks for it.
- DO NOT generate projects/practice tasks unless the user explicitly asks for projects/practice/tasks/portfolio.

Plan triggers (examples):
Arabic: "خطة" "مسار" "روودماب" "timeline" "step by step" "اعملّي خطة" "خطة مذاكرة" "learning path"
English: "plan" "roadmap" "timeline" "step by step" "learning path" "study plan"

If the user asked for a plan but DID NOT specify the topic/role/domain (e.g., "اعملي خطة مذاكرة" alone),
you MUST NOT generate any plan. Ask exactly ONE clarifying question: "خطة لموضوع إيه بالظبط؟" / "Plan for what exactly?"

4) Explainability / Traceability:
Every word you output MUST be justifiable by:
- user_query and/or conversation_context and/or retrieved_catalog_courses.

5) Skill Grounding (CRITICAL):
- Every skill you output MUST have:
  (a) a short "why" explaining why this skill is needed for the user goal, AND
  (b) at least 1 linked course_id from retrieved_catalog_courses.
- If you cannot link the skill to any course_id, do NOT output that skill at all.
- Never show "❓" or unknown placeholders.

6) Output Layout Rule (Two-Tier Courses):
You must produce TWO sections:
- "recommended_courses" (Top 1–3 most relevant courses only).
- "all_relevant_courses" (ALL relevant courses from retrieved_catalog_courses, no limit).
If the user says "غيرهم / more / other", you do NOT ask questions — just show more from all_relevant_courses
(if none left, say that is all available).

7) Language Mirror:
- If user is mainly Arabic → respond Arabic.
- If user is mainly English → respond English.
- Mixed → respond in the dominant language.

8) Safe Fallback (One Question Only):
If request is ambiguous, too broad, or confidence < 0.60:
- Return intent="SAFE_FALLBACK"
- Provide a short helpful line + ask exactly ONE clarifying question.
- No random courses.

9) Follow-up Behavior:
If user message is short like ("ياريت", "تمام", "yes", "ok") then treat it as answering the LAST pending question from context.
Do not switch topics unexpectedly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
B) INTENT POLICY (YOU MUST CHOOSE ONE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Choose exactly one intent:

- GENERAL_QA:
  Definitions/explanations: "what is X", "ايه هو X", "يعني ايه X"
  Output: short explanation only (no courses unless user asked for courses).

- COURSE_SEARCH:
  User asks explicitly for courses about a topic/skill: "كورسات عن...", "courses for..."
  Output: skills + courses. No plan unless requested.

- CAREER_GUIDANCE:
  User asks how to become/improve as a role without asking for a plan:
  "ازاي ابقى...", "how to become..."
  Output: required skills + courses. No plan unless requested.

- LEARNING_PATH:
  User explicitly asks for a plan/roadmap/timeline.
  Output: plan + courses (only if topic is clear). If topic unclear → ask one question only.

- CV_ANALYSIS:
  User uploads CV or asks for CV review/dashboard.

- SAFE_FALLBACK:
  Low confidence / unclear.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
C) RELEVANCE DEFINITION (WHAT IS “CORRECT”)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A course is relevant ONLY if it matches at least one of:
- core competency for the target role/topic
- essential tool/skill used in that role/topic
- tightly supporting skill (communication/leadership) ONLY if directly useful for the goal

Forbidden drift examples (unless user asked):
- Supply Chain, Operations, Agile, Programming, Project Mgmt, Ethics, etc.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
D) INPUTS YOU RECEIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You will receive:
- user_query: string
- conversation_context: optional dict (may include last_role, last_topic, pending_question)
- retrieved_catalog_courses: array of course objects (may be empty)
  Each has: course_id, title, level, category, instructor, short_desc

You can ONLY choose courses from retrieved_catalog_courses.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
E) OUTPUT: STRICT JSON ONLY (NO MARKDOWN)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Return exactly this schema:

{
  "intent": "GENERAL_QA|COURSE_SEARCH|CAREER_GUIDANCE|LEARNING_PATH|CV_ANALYSIS|SAFE_FALLBACK",
  "include_plan": true|false,
  "include_projects": true|false,
  "confidence": 0.0,
  "language": "ar|en|mixed",
  "role": "",
  "required_skills": {
    "core": [
      { "skill": "", "why": "", "course_ids": [""] }
    ],
    "supporting": [
      { "skill": "", "why": "", "course_ids": [""] }
    ]
  },
  "recommended_courses": [
    { "course_id": "", "title": "", "fit": "core|supporting", "why_recommended": "" }
  ],
  "all_relevant_courses": [
    { "course_id": "", "title": "", "fit": "core|supporting" }
  ],
  "learning_plan": null,
  "projects": [],
  "followup_question": ""
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
F) MODE ENFORCEMENT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- If include_plan=false:
  learning_plan MUST be null.
  followup_question:
    If user asked "ازاي ابقى..." (career guidance) ولم يطلب خطة:
      Ask ONE short question: "تحب خطة أسبوعية ولا ترشيح كورسات فقط؟" / "Do you want a weekly plan or courses only?"
    Otherwise keep followup_question = "".

- If include_projects=false:
  projects MUST be [].

- If retrieved_catalog_courses has no relevant matches:
  recommended_courses MUST be []
  all_relevant_courses MUST be []
  Ask ONE clarifying question (topic/role/scope).

- Top 1–3 only in recommended_courses.
- ALL relevant in all_relevant_courses (no limit).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G) FINAL SELF-CHECK (BEFORE YOU OUTPUT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Verify:
- JSON is valid, no extra text.
- No invented courses.
- No plan unless explicitly requested AND topic is clear.
- No projects unless explicitly requested.
- Every skill has why + course_ids, otherwise remove it.
- recommended_courses <= 3
- all_relevant_courses includes all relevant courses.
- Exactly ONE intent.
- If uncertain: SAFE_FALLBACK with exactly one question.

END.
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
    ) -> tuple:
        """
        Main response orchestration. 
        Returns (answer, projects, courses, skill_groups, learning_plan, cv_dashboard, all_relevant)
        """
        # Route strict CV Analysis
        if intent_result.intent == IntentType.CV_ANALYSIS:
             # Check if we have actual content to analyze
             is_command_only = len(user_message.split()) < 5
             if not skill_result.validated_skills and is_command_only:
                 answer = "أهلاً بك! لتقييم سيرتك الذاتية أو مشروعك، يرجى رفع الملف (PDF/Word) أو نسخ التفاصيل هنا. 📄"
                 return answer, [], [], [], None, None, []
                 
             return await self._build_cv_dashboard(user_message, skill_result)
        
        # V9 Fix: Explicit Handling for GENERAL_QA / Definitions
        elif intent_result.intent == IntentType.GENERAL_QA or (intent_result.intent == IntentType.CAREER_GUIDANCE and len(user_message.split()) < 6 and "?" in user_message and not skill_result.validated_skills):
             # Fast track for "What is Excel?" or "Explain Python"
             prompt = f"User asked: {user_message}\nAnswer briefly (2-3 sentences) defining the concept. Then suggest asking for a learning path if interested."
             try:
                 resp = await self.llm.generate_json(prompt, system_prompt="You are a helpful IT Tutor. Return JSON: {'answer': '...'}", temperature=0.3)
                 return resp.get("answer", "مفهوم مهم في المجال التقني."), [], [], [], None, None, []
             except:
                 return "هو مفهوم تقني يستخدم في تحليل البيانات وتطوير البرمجيات. تحب أرشحلك كورسات عنه؟", [], [], [], None, None, []
        
        else:
            # --- V10 Logic: LLM Decides Tiering ---
            # We send all filtered courses to the LLM (capped for token safety)
            courses_context = courses[:20] 
            
            # Initialize return variables
            answer = ""
            projects = []
            final_courses = []
            all_relevant = []
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
            
            session_state = {}
            if context:
                session_state = {
                    "last_intent": context.get("last_intent"),
                    "last_topic": context.get("last_topic"),
                    "pagination_offset": context.get("pagination_offset", 0),
                    "is_short_confirmation": context.get("is_short_confirmation", False),
                    "last_followup": context.get("last_followup", "")
                }

            prompt_context = ""
            if session_state.get("is_short_confirmation"):
                last_q = session_state.get("last_followup", "")
                prompt_context = f"\n[CONTEXT] User is confirming/answering your last question: \"{last_q}\". Stay in that scope."

            prompt = f"""User Message: "{user_message}"{prompt_context}
Intent identified: {intent_result.intent.value}
Target Role: {intent_result.role}

RETRIEVED DATA (Only use this):
retrieved_catalog_courses: {courses_data}
conversation_context: {session_state}

Generate the structured response in JSON format."""

            try:
                response = await self.llm.generate_json(
                    prompt=prompt,
                    system_prompt=RESPONSE_SYSTEM_PROMPT,
                    temperature=0.3
                )
                
                # Check Flags from LLM
                include_plan = response.get("include_plan", False)
                include_projects = response.get("include_projects", False)

                # 1. Answer Mapping
                answer = response.get("answer", "")
                if not answer:
                    role_desc = response.get("role", "")
                    if role_desc:
                         answer = f"**المسار المهني: {role_desc}**\n\n"
                
                followup = response.get("followup_question", "")
                self.last_followup_question = followup
                
                # 2. Skill Groups Processing (Strict Grounding)
                skills_req = response.get("required_skills", {})
                
                if skills_req:
                    for group_key, group_title, group_why in [
                        ("core", "Core Skills", "المهارات الأساسية"),
                        ("supporting", "Supporting Skills", "مهارات مساعدة")
                    ]:
                        raw_list = skills_req.get(group_key, [])
                        if raw_list:
                            rich_skills = []
                            for s in raw_list:
                                if isinstance(s, dict):
                                    skill_name = s.get("skill", s.get("name", ""))
                                    skill_why = s.get("why", "")
                                    mapping_ids = s.get("course_ids", [])
                                    
                                    if mapping_ids:
                                        rich_skills.append(SkillItem(
                                            name=skill_name,
                                            why=skill_why,
                                            course_ids=mapping_ids,
                                            courses_count=len(mapping_ids)
                                        ))
                            
                            if rich_skills:
                                skill_groups.append(SkillGroup(
                                    skill_area=group_title if response.get("language") != "ar" else group_why,
                                    why_it_matters="أهم المهارات المطلوبة لهذا الهدف",
                                    skills=rich_skills
                                ))

                # 3. Learning Plan (Strict)
                if include_plan:
                    plan_data = response.get("learning_plan")
                    if isinstance(plan_data, dict):
                        phases = []
                        for p in plan_data.get("phases", []):
                            phases.append(LearningPhase(
                                title=p.get("title", "Phase"),
                                weeks=str(p.get("weeks", "1")),
                                skills=p.get("skills", []),
                                deliverables=p.get("deliverables", [])
                            ))
                        learning_plan = LearningPlan(phases=phases)
                
                # 4. Projects (Strict)
                if include_projects:
                    projects = []
                    for p in response.get("projects", []):
                        projects.append(ProjectDetail(
                            title=p.get("title", "Project"),
                            difficulty=p.get("difficulty", "Beginner"),
                            description=p.get("description", ""),
                            deliverables=p.get("deliverables", []),
                            suggested_tools=p.get("suggested_tools", []),
                        ))

                # 5. Two-Tier Course Mapping
                for rc in response.get("recommended_courses", []):
                    cid = rc.get("course_id")
                    match = next((c for c in courses if c.course_id == cid), None)
                    if match:
                        c_copy = copy.deepcopy(match)
                        c_copy.fit = rc.get("fit", "core")
                        c_copy.why_recommended = rc.get("why_recommended", "")
                        final_courses.append(c_copy)
                
                for arc in response.get("all_relevant_courses", []):
                    cid = arc.get("course_id")
                    match = next((c for c in courses if c.course_id == cid), None)
                    if match:
                        c_copy = copy.deepcopy(match)
                        c_copy.fit = arc.get("fit", "supporting")
                        all_relevant.append(c_copy)
                
                if not final_courses and all_relevant:
                    final_courses = all_relevant[:3]

                return answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard, all_relevant

            except Exception as e:
                logger.error(f"Response building failed: {e}", exc_info=True)
                return "عذراً، حدث خطأ أثناء إعداد الرد. هل يمكنك المحاولة مرة أخرى؟", [], [], [], None, None, []

    async def _build_cv_dashboard(self, user_message: str, skill_result: SkillValidationResult) -> tuple:
        """Generate structured CV Dashboard with Rich UI Schema."""
        # Returns (answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard, all_relevant)
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

            return answer, projects, final_courses, [], None, dashboard_data, []
        except Exception as e:
            logger.error(f"CV Dashboard generation failed: {e}")
            return "عذراً، حدث خطأ أثناء تحليل السيرة الذاتية.", [], [], [], None, None, []

    async def build_fallback(
        self,
        user_message: str,
        topic: str
    ) -> tuple:
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
            return response.get("answer", "عذراً، هذا المجال غير متوفر حالياً."), [], [], [], None, None, []
        except Exception:
             return "عذراً، هذا الموضوع غير متوفر في الكتالوج حالياً.", [], [], [], None, None, []

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
        return f"لقيتلك الكورسات دي:\n{titles}", [], courses, [], None, None, []

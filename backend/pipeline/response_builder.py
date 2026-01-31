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
    SkillValidationResult, SkillGroup, LearningPlan, WeeklySchedule, LearningPhase,
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

RESPONSE_SYSTEM_PROMPT = """SYSTEM: You are Career Copilot Response Renderer (Production). You write the final JSON for the UI.

YOU DO NOT RETRIEVE COURSES. You only:
- explain briefly,
- output skill needs (core/supporting),
- and select up to 3 courses ONLY from retrieved_catalog_courses (if present).

NON-NEGOTIABLE:
1) STRICT JSON ONLY. No markdown. No extra text.
2) LANGUAGE LOCK:
   - Arabic/mixed user => all narrative fields in Arabic: answer, why, why_recommended, followup_question.
3) CATALOG STRICTNESS:
   - recommended_courses must be a subset of retrieved_catalog_courses IDs.
   - If retrieved_catalog_courses is empty OR topic is out-of-catalog => recommended_courses MUST be [].
4) NO RANDOMNESS:
   - Never recommend unrelated courses.
   - Never “fill” with any course just to show something.
5) MODE POLICY:
   - If intent=GENERAL_QA => mode="answer_only"
   - If intent=COURSE_SEARCH => mode="courses_only"
   - If intent=CAREER_GUIDANCE => mode="answer_only" unless user asked for courses explicitly, then "plan_and_courses" only if user asked for plan.
6) OUT-OF-CATALOG HONESTY:
   - If system says is_in_catalog=false or missing_domain_msg exists:
     - answer: explain it's not available in catalog.
     - followup_question: ask what closest goal they want (e.g., security? backend? data?).
     - recommended_courses MUST be [] (do not guess).
7) SKILL DISCIPLINE:
   - required_skills must be realistic for the detected role/topic.
   - For roles:
     - Data Engineer core: SQL, Data Modeling, ETL/ELT, Warehousing, Pipelines, Orchestration basics.
     - Web Developer core: HTML/CSS/JS, backend basics, databases, deployment basics.
     - HR core: Recruitment, Performance Mgmt, Labor basics, communication.
   - Never map Data Engineer to Django/Web frameworks unless user explicitly asked for web backend.

INPUT YOU RECEIVE (context):
- user_message
- intent
- validated_skills (from backend skill vocab)
- retrieved_catalog_courses: list of {course_id,title,description}

OUTPUT JSON SCHEMA:
{
  "intent": "GENERAL_QA|COURSE_SEARCH|CAREER_GUIDANCE|LEARNING_PATH|CV_ANALYSIS|CATALOG_BROWSING|SAFE_FALLBACK|EXPLORATION",
  "mode": "answer_only|courses_only|plan_and_courses|browsing|fallback|exploration_questions",
  "answer": "3-5 lines",
  "include_plan": true|false,
  "confidence": 0.0-1.0,
  "language": "ar|en|mixed",
  "role": "string",
  "required_skills": {
    "core": [{"skill": "string", "why": "string"}],
    "supporting": [{"skill": "string", "why": "string"}]
  },
  "recommended_courses": [
    {"course_id":"ID","title":"Title","fit":"core|supporting","why_recommended":"string"}
  ],
  "followup_question": "Exactly one question"
}"""""

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
        Main response orchestration. (Production V15: Crash-Proof + Deterministic Fast-Paths).
        """
        from data_loader import data_loader
        is_ar = data_loader.is_arabic(user_message)
        
        # --- REQUIREMENT A: DETERMINISTIC CATALOG BROWSING (LLM-FREE) ---
        if intent_result.intent == IntentType.CATALOG_BROWSING:
             return self._build_catalog_browsing_response(user_message, is_ar)

        # 1. Resolve Multi-Axis Information AND OUT-OF-CATALOG check (V16)
        missing_domain_msg = ""
        if semantic_result and hasattr(semantic_result, 'is_in_catalog') and not semantic_result.is_in_catalog:
             domain = semantic_result.missing_domain or "هذا المجال"
             # V19 RULE B: Hard Block for Out-of-Catalog (Prevent LLM hallucination)
             # Return prompt-less immediate fallback
             msg = f"للاسف مفيش مسار {domain} مباشر حالياً." if is_ar else f"Currently, we don't have a direct {domain} track."
             f_q = "تحب تختار مجال قريب؟" if is_ar else "Would you like to explore a related field?"
             return (
                 msg, [], [], [], None, None, [], 
                 None, "fallback", f_q, intent_result.intent.value
             )

        if intent_result.intent == IntentType.CV_ANALYSIS:
             return await self._build_cv_dashboard(user_message, skill_result)

        # Initialize return variables with strict types
        answer = ""
        projects = []
        final_courses = [] 
        all_relevant = []  
        skill_groups = []
        learning_plan = None
        cv_dashboard = None
        mode = "courses_only"
        f_q = "هل تحب تتعمق في جزء معين؟" if is_ar else "Would you like to deep dive?"

        courses_context = courses[:20] 
        courses_data = [
            {
                "course_id": str(c.course_id),
                "title": c.title,
                "description": (c.description[:200] + "...") if c.description else "",
            }
            for c in courses_context
        ]
            
        # Call LLM for narrative only
        # V19: Use V2 System Prompt
        try:
            response = await self.llm.generate_json(
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                prompt=f"""User Message: {user_message}
Intent: {intent_result.intent.value}
Validated Skills: {json.dumps(skill_result.validated_skills)}
Retrieved Catalog Courses: {json.dumps(courses_data)}""",
                temperature=0.3
            )
            
            # --- REQUIREMENT C: CRASH-PROOF EXTRACTION ---
            def _safe_l(data, k): return data.get(k, []) if isinstance(data.get(k), list) else []
            def _safe_d(data, k): return data.get(k, {}) if isinstance(data.get(k), dict) else {}
            
            answer = str(response.get("answer") or "جاهز للمساعدة!")

            # --- V19 Patch #3: Language Lock Post-Check (Fallback for English Drift) ---
            if is_ar:
                # If answer is mostly ASCII, it's probably English -> force Arabic fallback line
                ascii_ratio = sum(1 for ch in answer if ord(ch) < 128) / max(1, len(answer))
                if ascii_ratio > 0.85:
                    answer = "تمام! قولي هدفك بدقة (وظيفة/مجال) وأنا أرشحلك أفضل كورسات من الكتالوج."

            answer = (missing_domain_msg + answer) if missing_domain_msg else answer
            f_q = str(response.get("followup_question") or f_q)
            include_plan = bool(response.get("include_plan", False))
            
            if include_plan: mode = "plan_and_courses"
            elif intent_result.intent == IntentType.GENERAL_QA: mode = "answer_only"
            elif intent_result.intent == IntentType.CAREER_GUIDANCE: mode = "answer_only" # V19 Policy

            # 3. DETERMINISTIC SKILL mapping & COURSE selection
            sk_req = _safe_d(response, "required_skills")
            for area, label_ar, label_en in [("core", "المهارات الأساسية", "Core Skills"), ("supporting", "مهارات مساعدة", "Supporting Skills")]:
                 skills_list = _safe_l(sk_req, area)
                 rich_skills = []
                 for s in skills_list:
                      s_name = s.get("skill", "")
                      s_why = s.get("why", "")
                      norm = data_loader.validate_skill(s_name)
                      if norm:
                           matched = data_loader.get_courses_for_skill(norm)
                           cids = [str(m.get("course_id") if isinstance(m, dict) else m) for m in (matched or [])]
                           rich_skills.append(SkillItem(skill_key=norm, label=s_name, why=s_why, course_ids=cids, courses_count=len(cids)))
                           
                           # Add to visible courses (Top 3 logic)
                           for m in (matched or []):
                                cid = str(m.get("course_id") if isinstance(m, dict) else m)
                                c_obj = next((c for c in courses if str(c.course_id) == cid), None)
                                if c_obj and c_obj not in final_courses:
                                     c_copy = copy.deepcopy(c_obj)
                                     c_copy.fit = area
                                     c_copy.why_recommended = s_why
                                     if len(final_courses) < 3: final_courses.append(c_copy)
                                     elif c_copy not in all_relevant: all_relevant.append(c_copy)
                 
                 if rich_skills:
                      skill_groups.append(SkillGroup(skill_area=label_ar if is_ar else label_en, why_it_matters=label_ar if is_ar else label_en, skills=rich_skills))

            # --- V19 RULE A: Anti-Force-Fill (Only force-fill if strictly COURSE_SEARCH/IN_CATALOG) ---
            # If skill mapping didn't select enough courses, only fill if we are CONFIDENT intent is search.
            if not missing_domain_msg and intent_result.intent == IntentType.COURSE_SEARCH:
                if len(final_courses) < 3:
                    for c in courses:
                        if len(final_courses) >= 3:
                            break
                        # Avoid duplicates
                        if c.course_id not in [x.course_id for x in final_courses]:
                            c_copy = copy.deepcopy(c)
                            # Assign default fit if missing
                            if not c_copy.fit: c_copy.fit = "Best Match"
                            final_courses.append(c_copy)
            
            # Ensure all_relevant has everything else
            for c in courses:
                 if c.course_id not in [x.course_id for x in final_courses] and c.course_id not in [x.course_id for x in all_relevant]:
                      all_relevant.append(c)

        except Exception as e:
            logger.error(f"Response building failed: {e}")
            answer = "عذراً، حدث خطأ أثناء إعداد الرد. سأحاول مجدداً." if is_ar else "Sorry, an error occurred. I will try again."
            mode = "fallback"

        return answer, projects, final_courses, skill_groups, learning_plan, cv_dashboard, all_relevant, None, mode, f_q, intent_result.intent.value

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
             return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING"

        # 2. "I don't know" - Guided Discovery
        if any(kw in msg for kw in ["مش عارف", "don't know", "معرفش"]):
             top_6 = all_cats[:6] # Deterministic top 6
             cats = [CategoryDetail(name=c, why="مجال مشهور ومنصح به") for c in top_6]
             answer = "ولا يهمك! دي أكتر 6 مجالات مطلوبة عندنا. اختار اللي يشدك أكتر:" if is_ar else "No worries! Here are the top 6 trending tracks. Pick one:"
             f_q = "إيه أكتر مجال مهتم بيه من دول؟" if is_ar else "Which area interests you most?"
             return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING"

        # 3. Default: Full List
        cats = [CategoryDetail(name=c, why="تصفح القسم") for c in all_cats]
        answer = "دي كل الأقسام المتاحة عندنا. اختار أي واحد وهطلعلك تفاصيله:" if is_ar else "Here are all available categories. Pick one to explore:"
        f_q = "تختار أي قسم؟" if is_ar else "Which category would you like to explore?"
        return answer, [], [], [], None, None, [], CatalogBrowsingData(categories=cats, next_question=f_q), "category_explorer", f_q, "CATALOG_BROWSING"

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

            return answer, projects, final_courses, [], None, dashboard_data, [], None, None, None, "CV_ANALYSIS"
        except Exception as e:
            logger.error(f"CV Dashboard generation failed: {e}")
            return "عذراً، حدث خطأ أثناء تحليل السيرة الذاتية.", [], [], [], None, None, [], None, None, None, "CV_ANALYSIS"

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
            
        return answer, [], [], [], None, None, [], None, None, None, "SAFE_FALLBACK"

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
        return f"لقيتلك الكورسات دي:\n{titles}", [], courses, [], None, None, [], None, None, None, "COURSE_SEARCH"

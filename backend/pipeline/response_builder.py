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

RESPONSE_SYSTEM_PROMPT = """SYSTEM: Career Copilot (Zedny) — Production Unified Prompt v1

You are a career mentor + catalog course recommender.
You MUST follow ONE intent per response and output ONLY valid JSON that matches the API schema.

GLOBAL HARD RULES
1) LANGUAGE LOCK:
   - If session language is Arabic, ALWAYS respond in Arabic, even if the user types a single English word (e.g., "Design").
   - Switch to English ONLY if the user writes a full English sentence and the session language is not locked.

2) NO HALLUCINATION:
   - Never invent course titles. Courses come only from "Retrieved Courses" list provided to you.

3) ONE INTENT ONLY:
   - Output exactly one intent from:
     EXPLORATION, EXPLORATION_FOLLOWUP, CATALOG_BROWSING, COURSE_SEARCH, LEARNING_PATH, CAREER_GUIDANCE, FOLLOW_UP, GENERAL_QA, SAFE_FALLBACK

4) STRICT OUTPUT:
   - Output JSON only. No markdown. No extra text.

EXPLORATION FEATURE (Pre-Recommendation Assistant)
Trigger when user is unsure:
- Arabic triggers: "مش عارف", "تايه", "محتار", "ساعدني", "مش عارف اختار"
- English triggers: "I don't know", "help me choose"

Exploration Flow (Short Version — NO LOOPS)
A) If user goal is job quickly OR mentions work/job:
   - Skip asking "goal" and directly show domains as choices.
B) Domains must ALWAYS be shown as choices:
   ["Programming","Data Science","Marketing","Business","Design"]
C) After user picks a domain:
   - Ask for sub-track choices (provided by backend or inferred from catalog browsing context).
D) After user picks a sub-track:
   - Set flow_state_updates.topic = chosen sub-track
   - Set intent = "COURSE_SEARCH" (handoff)

COURSE_SEARCH RESPONSE RULES
- Show Top 3 courses only (from retrieved list).
- For each course, include a short Arabic reason in `why_recommended`.
- If retrieved list has fewer than 3, still show what exists and ask a follow-up question.

LEARNING_PATH RULES (Slot Filling)
If duration or daily_time missing:
- Ask exactly with choices:
  duration choices: ["أسبوع","أسبوعين","شهر","شهرين"]
  daily time choices: ["ساعة","ساعتين","3+"]
- Do NOT output learning_plan in that case (null).
If both are present:
- Output learning_plan.schedule with day_or_week, topics, tasks, deliverable.

SALES MANAGER SPECIAL RULE
If role implies "manager/مدير":
- Ensure recommendations include at least 1 course related to Leadership & Management (if available in retrieved list).

OUTPUT JSON SCHEMA (must match)
{
  "intent": "<INTENT>",
  "language": "ar" or "en",
  "answer": "...",
  "ask": null or {"question":"...","choices":[...]},
  "learning_plan": null or {...},
  "courses": [],
  "projects": [],
  "flow_state_updates": {...}
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
        Main response orchestration (Production V2.0: Unified Prompt v1).
        """
        from data_loader import data_loader
        context = context or {}
        
        # 1. LANGUAGE LOCK
        # If session language is Arabic, ALWAYS respond in Arabic.
        # Switch to English ONLY if the user writes a full English sentence and the session language is not locked.
        session_lang = context.get("language")
        is_ar_msg = data_loader.is_arabic(user_message)
        
        # Logic to determine response language
        if session_lang == "ar":
            res_lang = "ar"
        elif not session_lang:
            # First interaction
            res_lang = "ar" if is_ar_msg else "en"
        else:
            # Session is English, check if we should switch back to Arabic or stay
            # Rules: "Switch to English ONLY if the user writes a full English sentence and the session language is not locked."
            # This implies if they write Arabic, it might stick to Arabic.
            res_lang = "ar" if is_ar_msg else "en"
            
        is_ar = res_lang == "ar"
        
        # 2. RESOLVE INTENT (Rule 1 Overrides)
        intent = intent_result.intent
        
        # 3. SPECIAL HANDLERS (LLM-FREE OR SLOTTED)
        
        # CATALOG BROWSING (LLM-FREE)
        if intent == IntentType.CATALOG_BROWSING:
             return self._build_catalog_browsing_response(user_message, is_ar)

        # EXPLORATION (Rule 1F, 2-Exploration)
        if intent in [IntentType.EXPLORATION, IntentType.EXPLORATION_FOLLOWUP]:
             return self._handle_exploration_flow(user_message, context, is_ar)

        # 4. UNIFIED LLM PATH (COURSE_SEARCH, LEARNING_PATH, CAREER_GUIDANCE, etc.)
        
        # Prepare course context for LLM
        courses_data = [
            {"course_id": str(c.course_id), "title": c.title, "instructor": c.instructor, "category": c.category, "level": c.level}
            for c in courses[:5] # Provide up to 5 for context, prompt says Top 3
        ]
        
        # Prepare slots for slot filling check
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
            }
        }
        
        try:
            response = await self.llm.generate_json(
                system_prompt=RESPONSE_SYSTEM_PROMPT,
                prompt=f"Context: {json.dumps(prompt_context)}",
                temperature=0.0
            )
            
            answer = str(response.get("answer") or "")
            final_intent = response.get("intent") or intent
            res_lang = response.get("language") or res_lang
            
            # Extract Ask/Question
            ask_data = response.get("ask")
            from models import ChoiceQuestion
            ask = ChoiceQuestion(**ask_data) if ask_data and isinstance(ask_data, dict) else None
            
            # Map selected courses
            selected_course_ids = [str(c.get("course_id")) for c in response.get("courses", [])]
            final_courses = []
            for cid in selected_course_ids:
                matching = next((c for c in courses if str(c.course_id) == cid), None)
                if matching:
                    # Update why_recommended from LLM if provided
                    llm_course = next((c for c in response.get("courses", []) if str(c.get("course_id")) == cid), {})
                    c_copy = copy.deepcopy(matching)
                    c_copy.why_recommended = llm_course.get("why_recommended") or c_copy.why_recommended
                    final_courses.append(c_copy)
            
            # If no courses in JSON but we have retrieved ones for COURSE_SEARCH, take top 3
            if not final_courses and intent == IntentType.COURSE_SEARCH and courses:
                for c in courses[:3]:
                    c_copy = copy.deepcopy(c)
                    c_copy.why_recommended = "خيار ممتاز لبدايتك في هالمجال." if is_ar else "Excellent choice for your start in this field."
                    final_courses.append(c_copy)

            # Extract Learning Plan
            learning_plan = None
            lp_data = response.get("learning_plan")
            if lp_data:
                schedule = []
                for item in lp_data.get("schedule", []):
                    schedule.append(LearningItem(
                        day_or_week=item.get("day_or_week"),
                        topics=item.get("topics", []),
                        tasks=item.get("tasks", []),
                        deliverable=item.get("deliverable")
                    ))
                learning_plan = LearningPlan(
                    topic=lp_data.get("topic") or intent_result.topic,
                    duration=lp_data.get("duration") or duration,
                    time_per_day=lp_data.get("time_per_day") or daily_time,
                    schedule=schedule
                )

            # Flow State Updates
            state_updates = response.get("flow_state_updates") or {}
            state_updates["language"] = res_lang # Persist language lock
                
            return answer, [], final_courses, [], learning_plan, None, courses, None, "unified", ask, final_intent, state_updates

        except Exception as e:
            logger.error(f"Unified build failed: {e}")
            fallback_msg = "تمام، بس محتاج أعرف أكتر عن هدفك عشان أرشحلك أحسن حاجة؟" if is_ar else "Got it, but I'd love to know more about your goal to give you the best advice."
            return fallback_msg, [], [], [], None, None, [], None, "fallback", "", intent, {"language": res_lang}

    def _handle_exploration_flow(self, user_msg: str, context: dict, is_ar: bool) -> tuple:
        """
        Zedny Exploration Flow (Short Version).
        A) Detect Job Goal -> Immediate Domains
        B) Domains Choice -> Sub-tracks
        C) Sub-track -> COURSE_SEARCH
        """
        exp_state = context.get("exploration", {})
        if not exp_state: exp_state = {"step": 1}
        
        step = exp_state.get("step", 1)
        user = user_msg.lower()
        from models import ChoiceQuestion
        
        # Step 1: Detect Goal or Show Domains
        if step == 1:
            job_signals = ["اشتغل", "شغل", "وظيفة", "job", "work", "career", "كارير"]
            if any(s in user for s in job_signals) or exp_state.get("goal") == "Job":
                # Skip to domain selection
                exp_state["goal"] = "Job"
                exp_state["step"] = 2
                
                q = "اختار مجال من دول عشان أساعدك تبدأ بسرعة:" if is_ar else "Choose a domain to get started quickly:"
                choices = ["Programming", "Data Science", "Marketing", "Business", "Design"]
                ask = ChoiceQuestion(question=q, choices=choices)
                answer = q
                return answer, [], [], [], None, None, [], None, "exploration", ask, "EXPLORATION", {"exploration": exp_state}
            else:
                # Ask goal
                exp_state["step"] = 2
                q = "قولي، هدفك إيه حالياً؟" if is_ar else "Tell me, what is your goal?"
                choices = ["ألاقي شغل", "أطور نفسي", "أغير مجالي"] if is_ar else ["Find a job", "Develop skills", "Change career"]
                ask = ChoiceQuestion(question=q, choices=choices)
                answer = "أهلاً بيك! أنا كارير كوبايلوت ومكاني هنا عشان أساعدك تختار طريقك."
                return answer, [], [], [], None, None, [], None, "exploration", ask, "EXPLORATION", {"exploration": exp_state}

        # Step 2: Domain Selected -> Sub-tracks
        if step == 2:
            # Detect chosen domain
            choices = ["Programming", "Data Science", "Marketing", "Business", "Design"]
            chosen = None
            for c in choices:
                if c.lower() in user:
                    chosen = c
                    break
            
            if not chosen:
                # User didn't pick from list, re-ask or try fuzzy
                chosen = choices[0] # Fallback
            
            exp_state["interest"] = chosen
            exp_state["step"] = 3
            
            from data_loader import data_loader
            suggested_cats = data_loader.suggest_categories_for_topic(chosen, top_n=5)
            
            q = "أي مجال فرعي تحب تبدأ فيه؟" if is_ar else "Which sub-track would you like to explore?"
            ask = ChoiceQuestion(question=q, choices=suggested_cats)
            answer = f"جميل، في {chosen} عندنا كذا تخصص. تحب تبدأ في أنهي واحد؟" if is_ar else f"Great, in {chosen} we have several tracks. Which one interests you?"
            
            return answer, [], [], [], None, None, [], None, "exploration", ask, "EXPLORATION_FOLLOWUP", {"exploration": exp_state}

        # Step 3: Sub-track Selected -> Handoff to COURSE_SEARCH
        if step == 3:
            # Resolve sub-track
            from data_loader import data_loader
            all_cats = data_loader.get_all_categories()
            final_topic = exp_state.get("interest", "Programming")
            for cat in all_cats:
                if cat.lower() in user:
                    final_topic = cat
                    break
            
            state_updates = {
                "topic": final_topic,
                "track": final_topic,
                "exploration": {"stage": "locked"}
            }
            answer = f"تمام 👌 هطلعلك أهم الكورسات في {final_topic} دلوقتي." if is_ar else f"Got it! Here are the best courses for {final_topic}."
            return answer, [], [], [], None, None, [], None, "answer_only", None, "COURSE_SEARCH", state_updates

        return "تمام، تحب تبدأ بأنهي مجال؟", [], [], [], None, None, [], None, "answer_only", None, "EXPLORATION", {}

        # Final Transition: Switch to COURSE_SEARCH (after Step 3)
        # Rule: Domain Selection Lock (V21)
        final_topic = exp_state.get("interest", "Career Development")
        
        # Try to find a specific category in the user message
        from data_loader import data_loader
        all_cats = data_loader.get_all_categories()
        for cat in all_cats:
            if cat.lower() in user:
                final_topic = cat
                break

        state_updates = {
            "topic": final_topic,
            "track": final_topic,
            "active_flow": None,
            "exploration": {
                "stage": "locked",
                "chosen_domain": final_topic
            }
        }
        answer = f"تمام 👌 أنا حفظت إن اهتمامك بـ {final_topic}. هطلعلك أهم الكورسات في التخصص ده دلوقتي." if is_ar else f"Got it! I've locked your interest in {final_topic}. Here are the best courses for you."
        return answer, [], [], [], None, None, [], None, "answer_only", None, "COURSE_SEARCH", state_updates

    async def _build_cv_dashboard(self, user_message: str, skill_result: SkillValidationResult) -> tuple:
        """Dashboard generation kept for internal robustness."""
        # This can be refactored later or kept if still needed by other parts
        pass

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

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from app.schemas_career import PlanOutput, Playlist, Citation, PDFInfo, RecommendedCourseSchema

logger = logging.getLogger(__name__)

class ResponseComposer:
    @staticmethod
    def compose(
        session_id: UUID,
        intent: Any,
        role_info: Dict[str, Any],
        plan_data: Dict[str, Any],
        recommended_courses: List[RecommendedCourseSchema],
        lang_policy: str = "en"
    ) -> PlanOutput:
        """
        STEP 6 — RESPONSE STRATEGY
        Assemble the final PlanOutput JSON.
        Must include roadmap summary + ONE offer.
        """
        # Multilingual Roadmap Summary
        is_ar = lang_policy == "ar" or intent.language == "ar"
        
        if is_ar:
            summary = f"خارطة طريق مهنيّة لـ {role_info.get('role', 'الهدف الخاص بك')}.\n\n"
            summary += f"مهارات أساسية:\n- " + "\n- ".join(role_info.get("required_skills", [])[:5])
        else:
            summary = f"Career Roadmap for {role_info.get('role', 'your goal')}.\n\n"
            summary += f"Key Skills:\n- " + "\n- ".join(role_info.get("required_skills", [])[:5])

        # Decision on offer
        # If vague intent -> offer assessment or study plan
        # If clear intent -> offer courses or study plan
        if intent.confidence_level == "vague":
            offer = "Would you like to assess your current level to refine this roadmap?" if not is_ar else "هل تود تقييم مستواك الحالي لتحسين هذه الخارطة؟"
        else:
            offer = "We have relevant internal courses. Would you like to see a full study plan?" if not is_ar else "لدينا كورسات داخلية ذات صلة. هل تود رؤية خطة دراسية كاملة؟"

        # Format Playlist
        course_ids = [c.course_id for c in recommended_courses]
        playlist_status = "available" if plan_data["plan_type"] == "our_courses" else "partial"
        if not course_ids:
            playlist_status = "not_available"

        return PlanOutput(
            session_id=session_id,
            output_language="ar" if is_ar else "en",
            plan_type=plan_data["plan_type"],
            coverage_score=plan_data["coverage_score"],
            summary=f"{summary}\n\n{offer}",
            required_skills=role_info.get("required_skills", []),
            recommended_courses=recommended_courses,
            plan_weeks=plan_data["plan_weeks"],
            playlist=Playlist(status=playlist_status, course_ids=course_ids),
            citations=role_info.get("citations", []),
            confidence="high" if plan_data["coverage_score"] >= 0.7 else "medium",
            follow_up_questions=["هل هذا المسار هو ما كنت تبحث عنه؟" if is_ar else "Is this roadmap what you were looking for?"],
            pdf=None # PDF Info added if requested later
        )

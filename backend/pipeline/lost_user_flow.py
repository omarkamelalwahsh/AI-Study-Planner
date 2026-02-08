import logging
from typing import List, Dict, Any, Optional
from models import ChatResponse, NextAction, IntentType

logger = logging.getLogger(__name__)

# Canonical Diagnostic Questions for Lost User v2
LOST_USER_QUESTIONS_V2 = [
    {
        "question": "إيه أكتر نوع من المهام بيشدك في شغلك أو دراستك؟",
        "choices": [
            "A — حل المشكلات التقنية والأرقام",
            "B — تنظيم المشاريع والبيزنس",
            "C — التصميم وتنسيق الألوان والواجهات",
            "D — مساعدة الناس وكتابة المحتوى"
        ]
    },
    {
        "question": "لو قدامك يوم كامل فاضي، تحب تقضيه في إيه؟",
        "choices": [
            "A — اتعلم لغة برمجة أو أداة تحليل بيانات",
            "B — أخطط لمشروع جديد أو أذاكر إدارة",
            "C — أجرب أدوات تصميم أو أرسم فكرة",
            "D — أكتب مقال أو أتواصل مع ناس جديدة"
        ]
    },
    {
        "question": "إيه أكتر حاجة بتبسطك لما تخلصها؟",
        "choices": [
            "A — كود اشتغل صح أو معادلة اتحلت",
            "B — خطة مشروع جاهزة للتنفيذ",
            "C — شكل نهائي جميل وجذاب للمنتج",
            "D — تأثير إيجابي على شخص أو حملة ناجحة"
        ]
    },
    {
        "question": "بتحب تشتغل أكتر مع مين؟",
        "choices": [
            "A — مع الكمبيوتر والبيانات في هدوء",
            "B — مع فريق عمل وبقود التنفيذ",
            "C — مع فنانين ومصممين بيبدعوا فكرة",
            "D — مع جمهور ومستخدمين بفهم احتياجهم"
        ]
    },
    {
        "question": "إيه الهدف الأساسي ليك حالياً؟",
        "choices": [
            "A — أبني أنظمة قوية وأتطور تقنياً",
            "B — أكون مدير ناجح أو رائد أعمال",
            "C — أعمل تصاميم عالمية ومميزة",
            "D — أغير حياة الناس من خلال المحتوى أو الخدمة"
        ]
    }
]

TRACK_RECOMMENDATIONS = {
    "A": ["Software Development", "Data & AI", "Cybersecurity / IT"],
    "B": ["Product / Project Management", "Data & AI"],
    "C": ["UI/UX Design", "Graphic Design"],
    "D": ["Digital Marketing / Content", "Product / Project Management"]
}

ALLOWED_TRACKS = [
    "Software Development",
    "Data & AI",
    "Cybersecurity / IT",
    "Product / Project Management",
    "Digital Marketing / Content",
    "UI/UX Design"
]

TRACK_ALIASES = {
    "security": "Cybersecurity / IT",
    "cyber": "Cybersecurity / IT",
    "it": "Cybersecurity / IT",
    "software": "Software Development",
    "dev": "Software Development",
    "data": "Data & AI",
    "ai": "Data & AI",
    "marketing": "Digital Marketing / Content",
    "content": "Digital Marketing / Content",
    "design": "UI/UX Design",
    "ux": "UI/UX Design",
    "ui": "UI/UX Design",
    "product": "Product / Project Management",
    "project": "Product / Project Management"
}

ROADMAPS = {
    "Software Development": "أهلاً بيك في عالم البرمجة! 🚀\n\n**خريطة طريق لأول أسبوعين:**\n- **الأسبوع الأول:** اتعلم أساسيات البرمجة (Variables, Loops, Conditions) باستخدام لغة Python.\n- **الأسبوع الثاني:** ابني مشروع بسيط (Calculator أو To-Do List).\n\nالمسار ده ممتع جداً ومطلوب عالمياً.",
    "Data & AI": "عالم البيانات والذكاء الاصطناعي هو المستقبل! 📊\n\n**خريطة طريق لأول أسبوعين:**\n- **الأسبوع الأول:** اتعلم أساسيات الإحصاء واستخدام Excel بشكل احترافي.\n- **الأسبوع الثاني:** ابدأ اتعلم مكتبة NumPy و Pandas في لغة Python.\n\nالبيانات هي البترول الجديد!",
    "Cybersecurity / IT": "الأمن السيبراني هو خط الدفاع الأول! 🛡️\n\n**خريطة طريق لأول أسبوعين:**\n- **الأسبوع الأول:** اتعلم أساسيات الشبكات (Networking Concepts, IP, DNS).\n- **الأسبوع الثاني:** اتعلم مقدمة في Linux والـ Command Line.\n\nمجال Cybersecurity دايماً في تطور ومطلوب جداً.",
    "Product / Project Management": "لو بتحب التنظيم والقيادة، ده مجالك! 📋\n\n**خريطة طريق لأول أسبوعين:**\n- **الأسبوع الأول:** اتعلم أساسيات الـ Agile و Scrum.\n- **الأسبوع الثاني:** جرب تستخدم أدوات زي Jira أو Trello لتنظيم مشروع بسيط.\n\nالمديرين الناجحين هما اللي بيحركوا الفرق.",
    "Digital Marketing / Content": "التسويق الرقمي هو لغة العصر! 📣\n\n**خريطة طريق لأول أسبوعين:**\n- **الأسبوع الأول:** اتعلم أساسيات الـ Digital Marketing و الـ Consumer Behavior.\n- **الأسبوع الثاني:** ابدأ اتعلم الـ Meta Ads و الـ Content Strategy.\n\nالمحتوى هو الملك!",
    "UI/UX Design": "تصميم تجربة المستخدم هو اللي بيخلينا نحب البرامج! 🎨\n\n**خريطة طريق لأول أسبوعين:**\n- **الأسبوع الأول:** اتعلم أساسيات الـ Design Thinking ومبادئ الـ UI.\n- **الأسبوع الثاني:** ابدأ جرب أداة Figma وصمم أول واجهة موبايل.\n\nالعين بتشتري قبل أي حاجة!"
}

def parse_lost_user_answer(msg: str) -> Optional[str]:
    """Parses user input into canonical A, B, C, or D."""
    m = (msg or "").strip().upper()
    mapping = {
        "A": "A", "B": "B", "C": "C", "D": "D",
        "1": "A", "2": "B", "3": "C", "4": "D",
        "أ": "A", "ب": "B", "ج": "C", "د": "D",
    }
    if m in mapping: return mapping[m]
    
    m_lower = (msg or "").lower()
    if any(k in m_lower for k in ["تقني", "أكواد", "برمجة", "بيانات", "data", "tech"]): return "A"
    if any(k in m_lower for k in ["بيزنس", "إدارة", "تنظيم", "business", "manage"]): return "B"
    if any(k in m_lower for k in ["تصميم", "ألوان", "واجهة", "design", "ui", "ux"]): return "C"
    if any(k in m_lower for k in ["مساعدة", "محتوى", "ناس", "marketing", "content"]): return "D"
    return None

def parse_track_selection(msg: str, suggested: List[str]) -> Optional[str]:
    """Parses user selection of a track."""
    m_lower = (msg or "").lower()
    
    # Check aliases
    if track := next((track for alias, track in TRACK_ALIASES.items() if alias in m_lower), None):
        return track
            
    # Check direct names
    return next((track for track in ALLOWED_TRACKS if track.lower() in m_lower), None)

def get_lost_user_v2_response(session_id: str, session_state: Dict[str, Any], user_msg: Optional[str] = None) -> ChatResponse:
    """Main handler for LOST_USER_FLOW v2 (Phased Implementation)."""
    phase = session_state.get("phase", "questions")
    answers = session_state.get("answers", [])
    q_index = session_state.get("q_index", 0)
    suggested_tracks = session_state.get("suggested_tracks", [])

    # PHASE 1: QUESTIONS
    if phase == "questions":
        if user_msg and q_index < len(LOST_USER_QUESTIONS_V2):
            if ans := parse_lost_user_answer(user_msg):
                answers.append(ans)
                q_index += 1
                session_state["answers"] = answers
                session_state["q_index"] = q_index
            else:
                current_q = LOST_USER_QUESTIONS_V2[q_index]
                return ChatResponse(
                    intent=IntentType.CAREER_GUIDANCE,
                    answer="للأسف مفهمتش اختيارك 😅 ممكن تختار (A, B, C, D) أو ترد برقم الاختيار:\n\n" + 
                           f"**{current_q['question']}**\n\n" + "\n".join(current_q["choices"]),
                    next_actions=[NextAction(text="اختر A أو B أو C أو D", type="follow_up", payload={"flow": "lost_user_v2"})],
                    session_state=session_state
                )

        # Transition to Phase 2 (choose_track) if Q5 is answered
        if q_index >= len(LOST_USER_QUESTIONS_V2):
            from collections import Counter
            counts = Counter(answers)
            top_type = counts.most_common(1)[0][0]
            suggested_tracks = TRACK_RECOMMENDATIONS.get(top_type, ["Software Development"])
            
            session_state["phase"] = "choose_track"
            session_state["suggested_tracks"] = suggested_tracks
            
            tracks_str = "\n".join([f"- {t}" for t in suggested_tracks])
            return ChatResponse(
                intent=IntentType.CAREER_GUIDANCE,
                answer=f"بناءً على إجاباتك، أفضل مسارات مهنية ليك هي:\n\n{tracks_str}\n\nتحب نبدأ نكتشف أنهي مجال فيهم؟ (اكتب اسم المجال أو اختصاره)",
                next_actions=[NextAction(text=t, type="follow_up", payload={"track": t}) for t in suggested_tracks],
                session_state=session_state
            )

        # Standard Question Delivery
        q_data = LOST_USER_QUESTIONS_V2[q_index]
        intro = "عشان أساعدك صح، هسألك 5 أسئلة سريعة نفهم بيها ميولك. \n\n" if q_index == 0 else f"السؤال {q_index + 1} من 5:\n\n"
        return ChatResponse(
            intent=IntentType.CAREER_GUIDANCE,
            answer=f"{intro}**{q_data['question']}**\n\n" + "\n".join(q_data["choices"]),
            next_actions=[NextAction(text="اختيار من القائمة", type="follow_up", payload={"flow": "lost_user_v2"})],
            session_state={**session_state, "active_flow": "lost_user_v2", "phase": "questions", "q_index": q_index, "answers": answers}
        )

    # PHASE 2: CHOOSE TRACK
    if phase == "choose_track":
        if chosen := parse_track_selection(user_msg, suggested_tracks):
            session_state["phase"] = "done"
            session_state["chosen_track"] = chosen
            roadmap = ROADMAPS.get(chosen, "بالتوفيق في مسارك الجديد!")
            
            return ChatResponse(
                intent=IntentType.CAREER_GUIDANCE,
                answer=f"ممتاز! اختيارك لـ **{chosen}** اختيار ذكي جداً. 🌟\n\n{roadmap}\n\nتحب أعرضلك أهم الكورسات المتاحة في الكتالوج للمسار ده؟",
                next_actions=[
                    NextAction(text="عرض الكورسات المناسبة", type="course_search", payload={"topic": chosen}),
                    NextAction(text="اختيار مسار مختلف", type="follow_up", payload={"step": "choose_track_again"})
                ],
                session_state=session_state
            )
        else:
            tracks_str = "\n".join([f"- {t}" for t in suggested_tracks])
            return ChatResponse(
                intent=IntentType.CAREER_GUIDANCE,
                answer=f"من فضلك اختر واحد من المسارات دي:\n{tracks_str}",
                next_actions=[NextAction(text=t, type="follow_up", payload={"track": t}) for t in suggested_tracks],
                session_state=session_state
            )

    # RESTART Logic (Internal)
    if phase == "done" and user_msg and any(k in user_msg.lower() for k in ["مختلف", "تاني", "again", "change"]):
        session_state["phase"] = "choose_track"
        # Re-display suggested tracks
        tracks_str = "\n".join([f"- {t}" for t in suggested_tracks])
        return ChatResponse(
            intent=IntentType.CAREER_GUIDANCE,
            answer=f"مفيش مشكلة، دي المسارات المقترحة ليك:\n{tracks_str}\n\nتحب تكتشف أنهي واحد فيهم؟",
            next_actions=[NextAction(text=t, type="follow_up", payload={"track": t}) for t in suggested_tracks],
            session_state=session_state
        )

    return get_lost_user_v2_response(session_id, {**session_state, "phase": "questions", "q_index": 0})

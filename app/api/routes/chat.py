import os
import logging
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService, safe_uuid
from app.db import get_db, SessionLocal, engine

import json

logger = logging.getLogger("chat_route")
router = APIRouter()

CATEGORY_TERMS = {
    "design": "Graphic Design",
    "marketing": "Marketing Skills",
    "programming": "Programming",
    "business": "Business Fundamentals",
    "hr": "Human Resources",
    "sales": "Sales",
    "soft skills": "Soft Skills",
    "management": "Project Management",
    # Arabic aliases
    "برمجة": "Programming",
    "تصميم": "Graphic Design",
    "جرافيك": "Graphic Design",
    "تسويق": "Marketing Skills",
    "بيزنس": "Business Fundamentals",
    "ادارة": "Leadership & Management", 
    "قيادة": "Leadership & Management"
}

BASE_DIR = os.getcwd()
DATA_PATH = os.path.join(BASE_DIR, "data", "courses.csv")

chat_service: Optional[ChatService] = None
try:
    if os.path.exists(DATA_PATH):
        chat_service = ChatService(DATA_PATH)
        logger.info("ChatService initialized.")
    else:
        logger.warning(f"Data file not found at {DATA_PATH}")
except Exception as e:
    logger.exception(f"Failed to initialize ChatService: {e}")


def _sse_event(event_type: str, data: dict) -> str:
    payload = {"type": event_type, **data}
    json_str = json.dumps(payload, ensure_ascii=False)
    # Log first 200 chars only
    logger.info(f"SSE EMIT: {json_str[:200]}...")
    return f"data: {json_str}\n\n"


@router.post("/chat")
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    if not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not initialized (missing data).")

    session_id = safe_uuid(request.session_id)
    msgs = request.normalized_messages()
    if not msgs:
        raise HTTPException(status_code=400, detail="No messages provided.")

    last_message = msgs[-1].content.strip().lower()
    client_state = request.client_state or {}

    # 1. Broad "Yes/No" detection for Egyptian/Standard Slang
    def is_yes(text):
        yes_variants = {
            "نعم", "ايوه", "أيوه", "ماشي", "تمام", "يلا", "اوكى", "أوكي", "ماشي", "اوكي", 
            "مفيش مشكلة", "مفيش مشكله", "ماشي ياريت", "طبعاً", "طبعا", "اوكي ماشي",
            "باشا", "اشطة", "قشطة", "بيس", "خلصانة", "خلصانه", "امين", "أمين",
            "yes", "y", "yeah", "ok", "okay", "sure", "go ahead", "yep", "do it", "cool"
        }
        t = text.strip().lower()
        if t in yes_variants: return True
        # Check if message contains any of these as a standalone word
        words = t.split()
        if any(w in yes_variants for w in words):
            return True
        return False

    def is_no(text):
        no_variants = {"لا", "no", "n", "مش", "nope", "not now", "بلاش", "فكس"}
        t = text.strip().lower()
        return t in no_variants or any(t.startswith(v) for v in no_variants)
    
    # Check if we are waiting for study plan preferences
    if client_state.get("waiting_for_prefs"):
        # We are simply expecting a response about time/weeks, so we treat ANY non-no input as valid for parsing
        if not is_no(last_message):
            import re
            last_topic = client_state.get("last_topic")
            last_courses = client_state.get("last_courses") or []
            
            # Simple regex to find numbers
            # Look for 1-2 digits. If multiple numbers, first might be weeks, second hours or vice versa?
            # Let's assume context or keywords. 
            # Arabic keywords? "اسبوع", "ساعة"
            
            # Defaults
            weeks = 4
            hours = 10
            
            # Extract numbers from text
            try:
                # Find all integers
                nums = [int(n) for n in re.findall(r'\d+', last_message)]
                if len(nums) >= 2:
                    # User likely said "4 weeks, 10 hours" -> heuristic first is weeks usually if smaller? 
                    # Or based on keywords.
                    # Let's simple check keywords.
                    if "week" in last_message or "اسبوع" in last_message or "أسابيع" in last_message:
                         # Try to associate number with keyword? Too complex for regex.
                         # Fallback: First number is weeks, second is hours if provided.
                         weeks = nums[0]
                         hours = nums[1]
                    elif "hour" in last_message or "ساع" in last_message:
                         hours = nums[0]
                         # if there's second number...
                         if len(nums) > 1: weeks = nums[1]
                    else:
                         # Just numbers provided?
                         weeks = nums[0]
                         hours = nums[1]
                elif len(nums) == 1:
                     # Only one number. If > 10 likely hours? If < 12 likely weeks?
                     val = nums[0]
                     if val > 12:
                         hours = val
                         weeks = 4 # default
                     else:
                         weeks = val
                         hours = 10 # default
            except Exception:
                pass # Use defaults
                
            # Cap limits to be reasonable
            weeks = max(1, min(weeks, 24))
            hours = max(1, min(hours, 40))

            from app.core.formatting import build_study_plan
            is_ar = any("\u0600" <= c <= "\u06FF" for c in last_message)
            plan = build_study_plan(last_topic, last_courses, lang="ar" if is_ar else "en", num_weeks=weeks, hours_per_week=hours)
            
            if is_ar:
                msg = f"تمام يا بطل! عملتلك خطة مدتها {weeks} أسابيع بمعدل {hours} ساعة مذاكرة في الأسبوع لمسار {last_topic} 👇\n\n" + plan["text"]
            else:
                msg = f"Done! Created a {weeks}-week plan with {hours} hours/week for {last_topic} 👇\n\n" + plan["text"]
            
            # Done with flow, clear waiting state
            client_state["waiting_for_prefs"] = False
            
            return {
                "message": msg,
                "courses": [],
                "study_plan": plan["weeks"],
                "client_state": client_state
            }

    # Handle confirmation for study plan using client_state
    if is_yes(last_message):
        last_topic = client_state.get("last_topic")
        last_courses = client_state.get("last_courses") or []

        if last_topic and last_courses:
            # We have context. Now ASK for preferences instead of building immediately.
            msg = "تمام! تحب تخلص الكورسات دي في كام أسبوع؟ وتقدر تذاكر كام ساعة في الأسبوع؟"
            
            client_state["waiting_for_prefs"] = True
            
            return {
                "message": msg,
                "courses": [], # Don't show courses again, just the question
                "study_plan": [],
                "client_state": client_state
            }
        else:
            return {
                "message": "تمام. قولي عايز خطة لمسار إيه بالظبط؟ (بايثون / ديزاين / ماركتنج ...)",
                "courses": [],
                "study_plan": []
            }

    if is_no(last_message):
        return {
            "message": "تمام. تحب أرشحلك مسار تاني ولا محتاج مساعدة في حاجة تانية؟",
            "courses": [],
            "study_plan": []
        }

    # 2. Detect topic + language
    from app.core.retrieval import normalize_topic, get_courses_by_topic, flatten_grouped
    from app.core.formatting import build_definition, build_uses, format_courses, closure_question
    import pandas as pd
    
    df = pd.read_csv(DATA_PATH)
    topic, lang, intent_detected = normalize_topic(last_message)

    # 3. Category mode (limit 5 only, ask for track)
    if topic in CATEGORY_TERMS:
        category = CATEGORY_TERMS[topic]
        cat_df = df[df["category"].fillna("") == category].copy()
        cat_df = cat_df.drop_duplicates("title")
        sample = cat_df.head(5)

        courses_out = [
            {
                "course_id": r["course_id"],
                "title": r["title"],
                "category": r["category"],
                "level": r["level"],
                "instructor": r["instructor"],
            }
            for _, r in sample.iterrows()
        ]

        msg = (
            f"المجال ده كبير. دي عيّنة كورسات من الداتا (أقصى 5). "
            f"قولي أنت عايز Track أنهي جوّه {topic}؟"
        )
        return {
            "message": msg,
            "courses": courses_out,
            "study_plan": [],
            "client_state": {"last_topic": topic, "last_courses": courses_out}
        }

    # 4. Level Detection Helper
    def detect_level(text: str) -> Optional[str]:
        t = text.lower()
        # Advanced
        if any(w in t for w in ["advanced", "محترف", "متقدم", "خبير", "adv", "احترافي", "pro"]):
            return "Advanced"
        # Intermediate
        if any(w in t for w in ["intermediate", "متوسط", "medium", "inter", "نص نص"]):
            return "Intermediate"
        # Beginner
        if any(w in t for w in ["beginner", "beginner", "basic", "basics", "مبتدئ", "تأسيس", "بداية", "صفر", "from zero"]):
            return "Beginner"
        return None

    # 5. Topic/Track mode (NO LIMIT: return ALL)
    grouped = get_courses_by_topic(topic, df, max_per_level=None)
    
    # Filter by level if specified (Current Level + Higher)
    # Logic: "Beginning from X and up"
    # Beginner -> Beginner, Intermediate, Advanced
    # Intermediate -> Intermediate, Advanced
    # Advanced -> Advanced
    req_level = detect_level(last_message)
    courses_flat = []
    
    if req_level:
        # Define hierarchy
        levels = ["Beginner", "Intermediate", "Advanced"]
        try:
            start_idx = levels.index(req_level)
            allowed_levels = levels[start_idx:] # Slice from index to end
        except ValueError:
            allowed_levels = levels # Fallback
            
        for lvl in allowed_levels:
            if lvl in grouped:
                courses_flat.extend(grouped[lvl])
    else:
        courses_flat = flatten_grouped(grouped)

    if courses_flat:
        definition = build_definition(topic, lang)
        uses = build_uses(topic, lang)
        question = closure_question(lang)

        # ✅ Choice A: Keep message clean (definition + uses + question), let UI handle cards
        msg = f"{definition}\n\n{uses}\n\nلقيت لك {len(courses_flat)} كورس للمسار ده. {question}"
        
        # Persistence
        try:
            chat_service.ensure_session(db, session_id)
            chat_service.persist_user_message(db, session_id, last_message)
            from app.models import ChatMessage as DBChatMessage
            assistant_msg = DBChatMessage(session_id=session_id, role="assistant", content=msg)
            db.add(assistant_msg)
            db.commit()
        except:
            pass

        courses_payload = [
            {
                "course_id": c["course_id"],
                "title": c["title"],
                "category": c["category"],
                "level": c["level"],
                "instructor": c["instructor"],
            }
            for c in courses_flat
        ]

        return {
            "message": msg,
            "courses": courses_payload,
            "study_plan": [],
            "client_state": {"last_topic": topic, "last_courses": courses_payload}
        }
    
    # 🛑 BLOCK LLM IF INTENT DETECTED BUT NO COURSES FOUND
    if intent_detected:
        no_res_msg = (
            f"Sorry, I couldn't find any courses for '{topic}' in my database."
            if lang == "en"
            else f"آسف، مش لاقي كورسات لـ '{topic}' في الداتا بتاعتي حالياً."
        )
        return {
            "message": no_res_msg,
            "courses": [],
            "study_plan": [],
            "client_state": {}
        }

    # 5. Fallback Flow: LLM (Phase 4)
    try:
        chat_service.ensure_session(db, session_id)
        chat_service.persist_user_message(db, session_id, last_message)
    except Exception as e:
        logger.exception("Session/Persistence failed")
        raise HTTPException(status_code=500, detail=str(e))

    final_response = {
        "message": "",
        "courses": [],
        "study_plan": [],
        "client_state": client_state
    }

    try:
        async for chunk in chat_service.handle_message(session_id, last_message, db):
            if isinstance(chunk, dict):
                msg_content = chunk.get("text") or chunk.get("message") or chunk.get("assistant_message")
                if msg_content:
                    final_response["message"] += msg_content
                if chunk.get("courses"):
                    final_response["courses"] = chunk["courses"]
                if chunk.get("study_plan"):
                    final_response["study_plan"] = chunk["study_plan"]
            elif isinstance(chunk, str):
                final_response["message"] += chunk
    except Exception:
        logger.exception("Error producing chat response")
        return {"message": "حدث خطأ أثناء معالجة طلبك.", "courses": [], "study_plan": []}

    return final_response

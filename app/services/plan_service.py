import logging
import uuid
import math
from app.db import SessionLocal
from app.models import Plan, PlanWeek, PlanItem, Course, SearchQuery

logger = logging.getLogger(__name__)

def create_plan(query_text: str, query_id: int | None, weeks: int, hours_per_week: float, course_candidates: list[dict]):
    """
    Generates a study plan.
    course_candidates: list of dicts from search results (must have 'id' and 'duration_hours')
    Courses are sorted by level (beginner → intermediate → advanced) before distribution.
    """
    db = SessionLocal()
    try:
        if not query_id and query_text:
            # Create query entry if not exists (though usually passed from API)
            pass 

        with db.begin(): # Transaction start
            # 1. Create Plan
            plan_id = uuid.uuid4()
            plan = Plan(
                id=plan_id,
                query_id=query_id,
                weeks=weeks,
                hours_per_week=hours_per_week
            )
            db.add(plan)
            
            # 2. Filter and Sort Candidates by LEVEL first
            # Level priority: beginner (1) → intermediate (2) → advanced (3) → unknown (4)
            def level_priority(course):
                level = course.get('normalized_level', 'unknown')
                if level == 'beginner':
                    return 1
                elif level == 'intermediate':
                    return 2
                elif level == 'advanced':
                    return 3
                else:  # unknown
                    return 4
            
            # Sort by level priority, then by relevance score (higher score first)
            sorted_candidates = sorted(
                course_candidates, 
                key=lambda c: (level_priority(c), -c.get('score', 0))
            )
            
            valid_courses = []
            for c in sorted_candidates:
                dur = c.get('duration_hours')
                if not dur or math.isnan(dur):
                    dur = 5.0 # Default fallback
                valid_courses.append({
                    "id": uuid.UUID(c['id']),
                    "duration": float(dur)
                })
            
            # 3. Distribution Logic
            # Goal: Fill 'weeks' buckets with approx 'hours_per_week'
            
            buckets = [[] for _ in range(weeks)]
            bucket_hours = [0.0] * weeks
            
            current_week = 0
            
            for course in valid_courses:
                if current_week >= weeks:
                    break
                
                # Check if fits in current week?
                # Simple packing: Add until full, then next week.
                # Allow slight overflow if it's the only item or just fit it.
                
                if bucket_hours[current_week] + course['duration'] <= hours_per_week * 1.2: # 20% buffer
                    buckets[current_week].append(course['id'])
                    bucket_hours[current_week] += course['duration']
                else:
                    # Move to next week
                    current_week += 1
                    if current_week < weeks:
                         buckets[current_week].append(course['id'])
                         bucket_hours[current_week] += course['duration']
            
            # 4. Write Weeks and Items
            for i, week_items in enumerate(buckets):
                week_num = i + 1
                if not week_items: 
                    continue # Skip empty weeks or create empty? better create to show it's free.
                
                pw = PlanWeek(plan_id=plan_id, week_number=week_num)
                db.add(pw)
                db.flush() # get pw.id
                
                for idx, cid in enumerate(week_items):
                    pi = PlanItem(
                        plan_week_id=pw.id,
                        course_id=cid,
                        order_in_week=idx + 1
                    )
                    db.add(pi)
            
            # Transaction commits automatically at exit of 'with' block
            
            return str(plan_id)
            
    except Exception as e:
        logger.exception("Plan generation failed")
        raise e
    finally:
        db.close()

# AI Study Planner - Auto-Level Detection Implementation

## COMPLETE FILE MODIFICATIONS

### 1. E:\AI-Study-Planner\app\search\retrieval.py

**First 65 Lines (showing infer_user_level function):**

```python
import os
import json
import faiss
import numpy as np
import logging

from sqlalchemy import or_, true

from app.db import SessionLocal
from app.models import Course
from app.search.embedding import EmbeddingModel, expand_query, normalize_ar
from app.core.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


def infer_user_level(query: str) -> str:
    """
    Automatically detect user level from query text.
    Returns: "beginner", "intermediate", or "advanced"
    """
    if not query:
        return "beginner"  # Safe default
    
    query_lower = query.lower().strip()
    
    # Advanced signals (check first - most specific)
    advanced_signals = [
        "متقدم", "محترف", "خبير", "advanced", "expert", "pro", "professional",
        "optimization", "optimize", "performance tuning", "window function", 
        "query tuning", "indexing strategy", "complex queries", "production",
        "architecture", "design patterns", "best practices advanced"
    ]
    if any(signal in query_lower for signal in advanced_signals):
        return "advanced"
    
    # Intermediate signals
    intermediate_signals = [
        "متوسط", "intermediate", "mid-level", "mid level", 
        "بعد الأساسيات", "بعد ما اتعلمت", "بعد ما تعلمت",
        "joins", "aggregation", "group by", "subqueries", "procedures",
        "practice", "real project", "real-world", "more advanced than basics"
    ]
    if any(signal in query_lower for signal in intermediate_signals):
        return "intermediate"
    
    # Beginner signals
    beginner_signals = [
        "مبتدئ", "مبتدئ", "ابدأ", "بداية", "من الصفر", "لسه", "اول مرة",
        "beginner", "starter", "basics", "basic", "introduction", "intro", 
        "from zero", "from scratch", "للمبتدئين", "start learning",
        "first time", "never learned", "new to"
    ]
    if any(signal in query_lower for signal in beginner_signals):
        return "beginner"
    
    # Default to beginner (safe choice)
    return "beginner"


def normalize_level(level: str) -> str:
```

**Key Changes:**

- Added `infer_user_level()` function to auto-detect level from query keywords
- Modified `filter_by_user_level()` to use EXACT level matching (beginner sees ONLY beginner, not cumulative)
- Modified `SearchEngine.search()` to remove `top_k` parameter
- Added relevance threshold (0.3) to filter irrelevant courses
- Returns ALL relevant courses above threshold, no hard limit

---

### 2. E:\AI-Study-Planner\app\main.py

**Modified Search Endpoint (Lines 106-163):**

```python
@app.post("/search", response_class=HTMLResponse)
async def search_endpoint(
    request: Request,
    query_text: str = Form(...),
    weeks: int = Form(4),
    hours_per_week: float = Form(10),
    db: Session = Depends(get_db)
):
    normalized_query = normalize_ar(query_text)
    expanded = expand_query(normalized_query)
    
    # AUTO-DETECT user level from query
    from app.search.retrieval import infer_user_level
    detected_level = infer_user_level(query_text)
    
    logger.info(f"Search+Plan: '{query_text}' | Detected Level: '{detected_level}' | Weeks: {weeks}")
    
    # Log query
    sq = SearchQuery(raw_query=query_text, normalized_query=normalized_query)
    db.add(sq)
    db.commit()
    db.refresh(sq)
    
    # Search with AUTO-DETECTED level filtering - ALL relevant courses (no top_k)
    results = SearchEngine.search(query_text, user_level=detected_level)
    logger.info(f"Found {len(results)} relevant courses for query_id {sq.id}")
    
    # Group courses by level for display (only detected level will have courses)
    from app.search.retrieval import group_courses_by_level
    courses_grouped = group_courses_by_level(results)
    
    # Generate plan automatically using ALL filtered results
    plan = None
    try:
        plan_id = create_plan(query_text, sq.id, weeks, hours_per_week, results)
        logger.info(f"Plan created: {plan_id} with {len(results)} courses")
        
        # Fetch created plan with relationships
        plan = db.query(Plan).options(
            joinedload(Plan.weeks_obj).joinedload(PlanWeek.items).joinedload(PlanItem.course)
        ).filter(Plan.id == plan_id).first()
        
        # Sort weeks and items
        if plan:
            plan.weeks_obj.sort(key=lambda w: w.week_number)
            for w in plan.weeks_obj:
                w.items.sort(key=lambda i: i.order_in_week)
    except Exception as e:
        logger.exception("Plan generation failed")
        # Continue anyway to show search results
    
    return templates.TemplateResponse("unified_results.html", {
        "request": request,
        "courses_grouped": courses_grouped,
        "plan": plan,
        "query_id": sq.id,
        "query_text": query_text,
        "normalized_query": normalized_query,
        "total_found": len(results),
        "weeks": weeks,
        "hours_per_week": hours_per_week,
        "detected_level": detected_level  # Pass detected level to template
    })
```

**Key Changes:**

- Removed `user_level` and `top_k` form parameters
- Auto-detects level using `infer_user_level(query_text)`
- Passes `detected_level` to template for display

---

### 3. E:\AI-Study-Planner\app\templates\index.html

**Complete File (37 lines):**

```html
{% extends "base.html" %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card shadow">
            <div class="card-body">
                <h2 class="card-title text-center mb-4">ابحث عن دورتك القادمة</h2>
                <form action="/search" method="post">
                    <div class="mb-3">
                        <label for="query_text" class="form-label">ماذا تريد أن تتعلم؟</label>
                        <input type="text" class="form-control form-control-lg" id="query_text" name="query_text"
                            placeholder="مثلاً: تعلم جافاسكربت من الصفر" required value="{{ query_text }}">
                    </div>

                    <div class="row">
                        <div class="col-md-4 mb-3">
                            <label for="weeks" class="form-label">مدة الخطة (أسابيع)</label>
                            <input type="number" class="form-control" id="weeks" name="weeks" value="{{ weeks }}"
                                min="1">
                        </div>
                        <div class="col-md-4 mb-3">
                            <label for="hours_per_week" class="form-label">ساعات الدراسة/أسبوع</label>
                            <input type="number" class="form-control" id="hours_per_week" name="hours_per_week"
                                value="{{ hours_per_week }}" min="1">
                        </div>
                    </div>

                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary btn-lg">بحث وتخطيط</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

**Key Changes:**

- Removed user level dropdown completely
- Removed top_k input field
- Simplified form to only query, weeks, and hours

---

### 4. E:\AI-Study-Planner\app\templates\unified_results.html

**First 25 Lines (showing detected level badge):**

```html
{% extends "base.html" %}

{% block content %}
<div class="mb-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="/">الرئيسية</a></li>
            <li class="breadcrumb-item active">النتائج والخطة</li>
        </ol>
    </nav>
    <div class="d-flex justify-content-between align-items-center">
        <h3>نتائج البحث: <span class="text-primary">{{ query_text }}</span></h3>
        <div>
            <span class="badge bg-info fs-6 me-2">{{ total_found }} دورة</span>
            <span class="badge fs-6 {% if detected_level == 'beginner' %}bg-success{% elif detected_level == 'intermediate' %}bg-warning text-dark{% else %}bg-danger{% endif %}">
                المستوى المتوقع: 
                {% if detected_level == 'beginner' %}مبتدئ{% elif detected_level == 'intermediate' %}متوسط{% else %}متقدم{% endif %}
            </span>
        </div>
    </div>
    <p class="text-muted small mt-2">تم اكتشاف المستوى تلقائياً من استعلامك، ويتم عرض الدورات المناسبة لهذا المستوى فقط</p>
</div>
```

**Key Changes:**

- Added detected level badge (green for beginner, yellow for intermediate, red for advanced)
- Added explanation text that level was auto-detected
- Shows total courses found without top_k limit

---

## VERIFICATION COMMANDS

### Start Application (if not running)

```powershell
cd E:\AI-Study-Planner
python -m uvicorn app.main:app --reload --port 8000
```

### Test Cases

**Test 1: Beginner SQL Detection**

```
URL: http://localhost:8000
Query: "عاوز اتعلم sql مبتدئ"
Expected: Badge shows "مبتدئ" (green), ONLY beginner SQL courses shown
```

**Test 2: Intermediate SQL with Keywords**

```
Query: "عاوز اتعلم sql متوسط joins و aggregation"
Expected: Badge shows "متوسط" (yellow), ONLY intermediate SQL courses shown
```

**Test 3: Advanced SQL**

```
Query: "SQL advanced optimization window functions"
Expected: Badge shows "متقدم" (red), ONLY advanced SQL courses shown
```

**Test 4: No Level Keywords (Default to Beginner)**

```
Query: "python"
Expected: Badge shows "مبتدئ" (green), ONLY beginner Python courses shown
```

---

## DEMO CHECKLIST

✅ **Auto-Level Detection**: System detects level from Arabic/English keywords in query  
✅ **No Manual Selection**: Level dropdown completely removed from UI  
✅ **EXACT Level Filtering**: Shows ONLY courses matching detected level (not cumulative)  
✅ **All Relevant Courses**: Removed top_k limit, shows all courses with relevance >= 0.3  
✅ **Visual Feedback**: Colored badge shows detected level (green/yellow/red)  
✅ **Production-Safe**: Defaults to beginner if no signals detected  

---

## FILES MODIFIED

1. **E:\AI-Study-Planner\app\search\retrieval.py** - Added auto-detection, EXACT filtering, removed limits
2. **E:\AI-Study-Planner\app\main.py** - Modified search endpoint to use auto-detection
3. **E:\AI-Study-Planner\app\templates\index.html** - Removed level dropdown
4. **E:\AI-Study-Planner\app\templates\unified_results.html** - Added detected level badge

Total: 4 files modified, 0 new files created, system fully automatic.

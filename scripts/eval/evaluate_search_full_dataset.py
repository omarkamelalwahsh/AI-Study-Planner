# scripts/evaluate_search_full_dataset.py
import re
import json
from collections import defaultdict
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import Course  # Assuming app/models.py exists
from app.search.router import SearchRouter

# --------- Config ---------
TOP_K = 20

STRICT_KEYWORDS = {
    "python","java","javascript","js","typescript","ts","php","ruby","go","rust",
    "sql","mysql","postgres","postgresql","mongodb","nosql",
    "react","node","nodejs","django","flask","fastapi","laravel",
    "linux","git","docker","kubernetes","k8s",
    "cyber","security","hacking",
}

AR_TO_EN = {
    "بايثون": "python",
    "جافا": "java",
    "جافاسكريبت": "javascript",
    "جافا سكريبت": "javascript",
    "ريأكت": "react",
    "ريأكتjs": "react",
    "اس كيو ال": "sql",
    "SQL": "sql",
    "ماي اس كيو ال": "mysql",
    "مايسكيول": "mysql",
    "دجانجو": "django",
    "فلاسك": "flask",
    "فاستapi": "fastapi",
    "لينكس": "linux",
    "جيت": "git",
    "دوكر": "docker",
}

LEVEL_EN = ["Beginner", "Intermediate", "Advanced"]
LEVEL_AR_TO_EN = {"مبتدئ": "Beginner", "متوسط": "Intermediate", "متقدم": "Advanced"}
LEVEL_EN_TO_AR = {"Beginner": "مبتدئ", "Intermediate": "متوسط", "Advanced": "متقدم"}

# --------- Helpers ---------
def norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def course_blob(c: Course) -> str:
    # Adjust fields based on your Course model
    return norm(
        f"{getattr(c,'title','') or ''} "
        f"{getattr(c,'category','') or ''} "
        f"{getattr(c,'level','') or ''} "
        f"{getattr(c,'skills','') or ''} "
        f"{getattr(c,'description','') or ''}"
    )

def get_course_id(item):
    # supports dict / ORM
    if isinstance(item, dict):
        return item.get("id") or item.get("course_id") or item.get("uuid")
    return getattr(item, "id", None)

def get_course_title(item):
    if isinstance(item, dict):
        return item.get("title")
    return getattr(item, "title", "")

def extract_keywords_from_course(c: Course):
    blob = course_blob(c)
    hits = set()
    for kw in STRICT_KEYWORDS:
        if kw in blob:
            hits.add(kw)
    return hits

def expected_courses_for_keyword(courses, keyword: str, level: str | None = None):
    out = []
    # If using robust tokenization in strict mode, we should ideally use it here too for Ground Truth.
    # But simple substring check is a decent baseline for "minimum expected".
    # For alias correctness: if course has 'javascript', keyword 'js', does substring match? No.
    # So we need smarter ground truth matching for aliases if we want fair strict recall.
    # We'll use simple substring for now as per user storage, but handle known aliases manually for GT?
    # No, let's keep it simple as user provided.
    
    # Actually, for 'js' keyword, if course has 'javascript' but not 'js', substring fails.
    # But router SHOULD find it. So Ground Truth might be UNDER-reporting if we rely only on substring.
    # Let's trust the user's provided script logic for now to avoid over-engineering the test 
    # unless it proves problematic.
    
    for c in courses:
        if level and (getattr(c, "level", None) != level):
            continue
        
        # IMPROVEMENT for Ground Truth: Basic Alias Check for common ones
        blob = course_blob(c)
        matches = False
        if keyword in blob:
            matches = True
        elif keyword == "js" and "javascript" in blob: matches = True
        elif keyword == "ts" and "typescript" in blob: matches = True
        elif keyword == "py" and "python" in blob: matches = True
        
        if matches:
            out.append(c)
    return out

def expected_courses_for_category(courses, category: str, level: str | None = None):
    out = []
    for c in courses:
        if level and (getattr(c, "level", None) != level):
            continue
        # Loose match for category Ground Truth
        c_cat = norm(getattr(c, "category", ""))
        target_cat = norm(category)
        if target_cat == c_cat: 
            out.append(c)
        elif target_cat in c_cat: # partial category match
             out.append(c)
             
    return out

def run_query(q: str):
    try:
        resp = SearchRouter.route_query(q)
        results = resp.get("results", []) or []
        ids = []
        for r in results[:TOP_K]:
            cid = get_course_id(r)
            if cid is not None:
                try: 
                    ids.append(int(cid)) # Ensure int if ID is int
                except:
                    ids.append(str(cid))
        return resp, ids, results[:TOP_K]
    except Exception as e:
        print(f"Error running query '{q}': {e}")
        return {}, [], []

def precision_recall(pred_ids, exp_ids):
    # Normalize IDs to strings for comparison safety
    pred = set(str(x) for x in pred_ids)
    exp = set(str(x) for x in exp_ids)
    
    if not pred and not exp:
        return 1.0, 1.0
    if not pred:
        return 0.0, 0.0
    
    tp = len(pred & exp)
    precision = tp / max(len(pred), 1)
    recall = tp / max(len(exp), 1)
    return precision, recall

# --------- Query generators ---------
def gen_keyword_queries(keyword_en: str):
    # English
    qs = [
        keyword_en,
        f"learn {keyword_en}",
        f"{keyword_en} course",
        f"{keyword_en} beginner",
    ]
    # Arabic (mapped)
    ar_forms = [k for k,v in AR_TO_EN.items() if v == keyword_en]
    for ar in ar_forms[:2]:
        qs += [
            ar,
            f"عاوز اتعلم {ar}",
            f"عاوز كورس {ar} مبتدئ",
        ]
    # Mixed
    qs += [
        f"عاوز اتعلم {keyword_en} مبتدئ",
        f"learn {keyword_en} مبتدئ",
    ]
    return list(dict.fromkeys(qs))  # unique preserve order

def gen_category_queries(category: str):
    # English baseline (exact category text)
    qs = [category]
    # Mixed variations
    qs += [
        f"courses in {category}",
        f"{category} beginner",
        f"{category} {LEVEL_EN_TO_AR.get('Beginner','مبتدئ')}",
    ]
    return list(dict.fromkeys(qs))

def gen_title_queries(title: str):
    t = title.strip()
    if not t:
        return []
    return list(dict.fromkeys([
        t,
        t.lower(),
        f"course {t}",
        f"كورسات {t}",
        f"عاوز {t}",
    ]))

# --------- Main evaluation ---------
def main():
    if not os.path.exists("data"):
        os.makedirs("data")

    session = SessionLocal()
    courses = session.query(Course).all()

    print("\n--- FULL DATASET SEARCH EVAL ---")
    print(f"Courses loaded: {len(courses)}")
    print(f"TOP_K: {TOP_K}\n")

    # Index helper maps
    by_id = {getattr(c, "id"): c for c in courses if getattr(c, "id", None) is not None}
    all_ids = set(by_id.keys())

    # --------- 1) Exact Title Tests (sample from dataset) ---------
    print("Running Title Tests...")
    title_tests = []
    for c in courses:
        title = getattr(c, "title", "")
        if title and len(title.strip()) >= 6:
            title_tests.append(c)
    # limit to avoid massive runtime using random sample ideally, but here just slice
    title_tests = title_tests[:80]

    hit1 = 0
    hit5 = 0
    total_title = 0

    for c in title_tests:
        total_title += 1
        q = getattr(c, "title", "")
        # print(f"  Title Q: {q}")
        resp, pred_ids, top_items = run_query(q)
        cid = getattr(c, "id", None)
        
        # Normalize IDs
        pred_ids_str = [str(x) for x in pred_ids]
        cid_str = str(cid)

        if pred_ids_str and pred_ids_str[0] == cid_str:
            hit1 += 1
        if cid_str in pred_ids_str[:5]:
            hit5 += 1

    # --------- 2) Keyword Strict Tests (auto from dataset keywords) ---------
    print("Running Keyword Tests...")
    keyword_pool = defaultdict(int)
    for c in courses:
        for kw in extract_keywords_from_course(c):
            keyword_pool[kw] += 1

    # keep keywords that actually exist in data
    existing_keywords = [kw for kw,count in keyword_pool.items() if count >= 2]
    existing_keywords.sort(key=lambda k: keyword_pool[k], reverse=True)
    existing_keywords = existing_keywords[:25]  # cap

    kw_precision_sum = 0.0
    kw_recall_sum = 0.0
    kw_cases = 0

    # --------- 3) Category Tests (all categories) ---------
    print("Running Category Tests...")
    categories = sorted({(getattr(c, "category", "") or "").strip() for c in courses if getattr(c, "category", "")})
    cat_recall_sum = 0.0
    cat_cases = 0

    # --------- Run Keyword Queries ---------
    keyword_debug_samples = []
    for kw in existing_keywords:
        exp = expected_courses_for_keyword(courses, kw)
        exp_ids = [getattr(x, "id") for x in exp if getattr(x, "id", None) is not None]

        for q in gen_keyword_queries(kw):
            kw_cases += 1
            resp, pred_ids, top_items = run_query(q)
            p, r = precision_recall(pred_ids, exp_ids)
            kw_precision_sum += p
            kw_recall_sum += r

            # keep some debug examples of fails
            if r < 0.2:
                keyword_debug_samples.append({
                    "query": q,
                    "keyword": kw,
                    "expected_count": len(exp_ids),
                    "pred_titles": [get_course_title(x) for x in top_items],
                    "route": resp.get("route"),
                    "status": resp.get("status"),
                    "debug_reason": resp.get("debug_reason"),
                    "parsed_strict": resp.get("parsed_query", {}).get("reasoning")
                })
                if len(keyword_debug_samples) >= 10:
                    pass 

    # --------- Run Category Queries ---------
    cat_debug_samples = []
    for cat in categories[:40]:  # cap to 40 categories for speed
        exp = expected_courses_for_category(courses, cat)
        exp_ids = [getattr(x, "id") for x in exp if getattr(x, "id", None) is not None]
        if len(exp_ids) < 2:
            continue

        for q in gen_category_queries(cat):
            cat_cases += 1
            resp, pred_ids, top_items = run_query(q)
            _, r = precision_recall(pred_ids, exp_ids)  # recall is what we care
            cat_recall_sum += r

            if r < 0.3:
                cat_debug_samples.append({
                    "query": q,
                    "category": cat,
                    "expected_count": len(exp_ids),
                    "pred_count": len(pred_ids),
                    "pred_titles": [get_course_title(x) for x in top_items],
                    "route": resp.get("route"),
                    "status": resp.get("status"),
                    "debug_reason": resp.get("debug_reason"),
                })
                if len(cat_debug_samples) >= 10:
                    pass

    # --------- Summary ---------
    def pct(x): return round(x * 100, 2)

    title_hit1 = hit1 / max(total_title, 1)
    title_hit5 = hit5 / max(total_title, 1)

    kw_prec = kw_precision_sum / max(kw_cases, 1)
    kw_rec = kw_recall_sum / max(kw_cases, 1)

    cat_rec = cat_recall_sum / max(cat_cases, 1) if cat_cases else 0.0

    report = {
        "meta": {"courses": len(courses), "TOP_K": TOP_K},
        "exact_title": {"total": total_title, "hit@1": hit1, "hit@5": hit5, "hit1%": pct(title_hit1), "hit5%": pct(title_hit5)},
        "keyword_strict": {"cases": kw_cases, "avg_precision@k": round(kw_prec, 4), "avg_recall@k": round(kw_rec, 4),
                           "precision%": pct(kw_prec), "recall%": pct(kw_rec),
                           "keywords_tested": existing_keywords},
        "category": {"cases": cat_cases, "avg_recall@k": round(cat_rec, 4), "recall%": pct(cat_rec), "categories_tested": len(categories[:40])},
        "debug_samples": {
            "keyword_low_recall_examples": keyword_debug_samples,
            "category_low_recall_examples": cat_debug_samples,
        }
    }

    print("\n--- SUMMARY ---")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    out_path = "data/search_eval_full_dataset_report.json"
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nSaved report -> {out_path}")
    except Exception as e:
        print(f"\nCould not save report: {e}")

    session.close()


if __name__ == "__main__":
    main()

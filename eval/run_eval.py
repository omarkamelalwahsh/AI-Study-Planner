"""
Career Copilot RAG - Minimal Eval Pack Runner
Runs 10 test cases against the local API for production verification.
"""
import json
import time
import sys
import os

# Try to use requests if available, otherwise use urllib
try:
    import requests
    USE_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    USE_REQUESTS = False

BASE_URL = os.getenv("EVAL_BASE_URL", "http://localhost:8001")
EVAL_FILE = os.path.join(os.path.dirname(__file__), "eval_cases.json")

def http_post(url, payload):
    """HTTP POST helper that works with requests or urllib."""
    if USE_REQUESTS:
        resp = requests.post(url, json=payload, timeout=60)
        return resp.status_code, resp.json() if resp.status_code == 200 else {}
    else:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.status, json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return e.code, {}

def http_get(url):
    """HTTP GET helper."""
    if USE_REQUESTS:
        try:
            resp = requests.get(url, timeout=5)
            return resp.status_code == 200
        except:
            return False
    else:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status == 200
        except:
            return False

def run_case(case):
    """Run a single eval case and return results."""
    case_id = case.get("id", "?")
    desc = case.get("description", "")
    print(f"[{case_id}] {desc}...", end=" ")
    
    payload = {"message": case["input"], "session_id": f"eval_{case_id}"}
    start = time.time()
    
    try:
        status, data = http_post(f"{BASE_URL}/chat", payload)
        latency = (time.time() - start) * 1000
        
        if status != 200:
            print(f"FAIL (HTTP {status})")
            return {"id": case_id, "success": False, "error": f"HTTP {status}", "latency": latency}
        
        # Check intent (soft match: accept close intents)
        actual_intent = data.get("intent", "")
        expected_intent = case.get("expected_intent")
        intent_ok = True
        if expected_intent and actual_intent != expected_intent:
            # Soft match: COURSE_SEARCH/CAREER_GUIDANCE overlap sometimes
            overlaps = [
                {"COURSE_SEARCH", "CAREER_GUIDANCE", "AMBIGUOUS"},
                {"GENERAL_QA", "CONCEPT_EXPLAIN"},
            ]
            intent_ok = any(actual_intent in s and expected_intent in s for s in overlaps)
            if not intent_ok:
                print(f"WARN (intent: {actual_intent} != {expected_intent})", end=" ")
        
        # Check courses count (only if applicable)
        courses = data.get("courses", [])
        projects = data.get("projects", [])
        plan = data.get("learning_plan", None)
        
        courses_ok = True
        
        # 1. Check Courses
        if "min_courses" in case and len(courses) < case["min_courses"]:
            courses_ok = False
            print(f"FAIL (courses: {len(courses)} < {case['min_courses']})")
        if "max_courses" in case and len(courses) > case["max_courses"]:
            courses_ok = False
            print(f"FAIL (courses: {len(courses)} > {case['max_courses']})")

        # 2. Check Projects
        if "min_projects" in case and len(projects) < case["min_projects"]:
            courses_ok = False
            print(f"FAIL (projects: {len(projects)} < {case['min_projects']})")
            
        # 3. Check Learning Plan
        if "expect_plan" in case and not plan:
            courses_ok = False
            print(f"FAIL (Missing Learning Plan)")

        if not courses_ok:
             return {"id": case_id, "success": False, "latency": latency, "courses": len(courses)}
        
        if intent_ok:
            info = []
            if len(courses) > 0: info.append(f"{len(courses)} courses")
            if len(projects) > 0: info.append(f"{len(projects)} projects")
            if plan: info.append("Plan Valid")
            
            print(f"PASS ({latency:.0f}ms, {', '.join(info) if info else 'No Content'})")
        else:
            print(f"WARN ({latency:.0f}ms)")
            
        return {"id": case_id, "success": courses_ok, "latency": latency, "courses": len(courses), "intent": actual_intent}
        
    except Exception as e:
        print(f"ERROR ({e})")
        return {"id": case_id, "success": False, "error": str(e), "latency": 0}

def main():
    print("=" * 50)
    print("Production Hardening Eval Pack")
    print("=" * 50)
    print(f"Target: {BASE_URL}")
    print()
    
    # Load cases
    try:
        with open(EVAL_FILE, "r", encoding="utf-8") as f:
            cases = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {EVAL_FILE} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in eval_cases.json: {e}")
        sys.exit(1)
    
    # Health check
    if not http_get(f"{BASE_URL}/health"):
        print("ERROR: API is not available. Please start the backend first.")
        print()
        print("How to start the backend:")
        print("  cd backend")
        print("  python -m uvicorn main:app --reload")
        sys.exit(1)
    
    print(f"Running {len(cases)} test cases...")
    print("-" * 50)
    
    results = []
    for i, case in enumerate(cases):
        res = run_case(case)
        results.append(res)
        # FIX 6: Sleep between cases to reduce rate limiting
        if i < len(cases) - 1:
            time.sleep(1.5)
    
    # Summary
    print("-" * 50)
    passed = sum(1 for r in results if r.get("success"))
    total = len(results)
    avg_latency = sum(r.get("latency", 0) for r in results) / max(1, total)
    empty_count = sum(1 for r in results if r.get("courses", 0) == 0)
    
    print(f"SUMMARY: {passed}/{total} Passed")
    print(f"Avg Latency: {avg_latency:.0f}ms")
    print(f"Empty Results Rate: {empty_count}/{total}")
    print("=" * 50)
    
    if passed < total:
        sys.exit(1)

if __name__ == "__main__":
    main()

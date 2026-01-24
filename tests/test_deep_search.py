
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.skills import analyze_career_request
from app.utils.skill_index import find_skill_matches, load_index_into_memory

async def test_deep_search():
    print("--- 1. Testing Deep Analysis (4+ Queries) ---")
    user_input = "how to become a good sales manager"
    print(f"Input: {user_input}")
    
    try:
        analysis = analyze_career_request(user_input)
        print(f"Analysis Result: {analysis}")
    except Exception as e:
        print(f"Analysis Failed (using Mock): {e}")
        # Mocking 4 queries per area
        analysis = {
            "target_role": "Sales Manager",
            "skill_areas": [
                {
                    "area_name": "Strategic Planning", 
                    "search_keywords": ["Strategic Planning", "Business Strategy", "Sales Forecasting", "Market Analysis"]
                }
            ]
        }
    
    print("\n--- 2. Testing Deep Retrieval (Evidence) ---")
    skill_areas = analysis.get("skill_areas", [])
    load_index_into_memory()
    
    for area in skill_areas:
        area_name = area.get("area_name")
        keywords = area.get("search_keywords", [])
        print(f"> Area: {area_name}")
        print(f"  Keywords: {keywords}")
        
        area_evidence = {}
        
        for kw in keywords:
            matches = find_skill_matches(kw)
            if matches:
                # Top 2 matches per keyword logic
                top_matches = matches[:2]
                for m in top_matches:
                    score = m.get("score", 0)
                    key = m.get("key", "")
                    c_ids = m.get("course_ids", [])[:3]
                    
                    for item in c_ids:
                        tid = item.get("course_id") if isinstance(item, dict) else item
                        tid_str = str(tid)
                        
                        if tid_str not in area_evidence:
                            area_evidence[tid_str] = {"queries": set(), "score": score}
                        
                        area_evidence[tid_str]["queries"].add(f"{kw} (matched '{key}')")
                        if score > area_evidence[tid_str]["score"]:
                            area_evidence[tid_str]["score"] = score

        # Results
        sorted_ids = sorted(area_evidence.keys(), key=lambda x: area_evidence[x]["score"], reverse=True)
        print(f"  => Found {len(sorted_ids)} unique courses.")
        
        for cid in sorted_ids[:3]:
            ev = area_evidence[cid]
            q_list = list(ev["queries"])
            print(f"     - Course {cid} | Score: {ev['score']} | Evidence: {q_list}")
            
    print("\n--- Test Complete ---")

if __name__ == "__main__":
    asyncio.run(test_deep_search())

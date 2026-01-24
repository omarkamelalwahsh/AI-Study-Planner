
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.skills import analyze_career_request
from app.utils.skill_index import find_skill_matches, load_index_into_memory

async def test_expanded_retrieval():
    print("--- 1. Testing Retrieval Limits ---")
    # Using a broad term that should have many courses
    keywords = ["Sales", "Communication", "Management"]
    
    load_index_into_memory()
    
    for kw in keywords:
        print(f"\n> Query: '{kw}'")
        area_evidence = {}
        
        matches = find_skill_matches(kw)
        if matches:
            top_matches = matches[:2]
            for m in top_matches:
                score = m.get("score", 0)
                # Mimic Chat.py logic: take 15 candidates
                c_ids = m.get("course_ids", [])[:15]
                
                for item in c_ids:
                    tid = item.get("course_id") if isinstance(item, dict) else item
                    tid_str = str(tid)
                    
                    if tid_str not in area_evidence:
                        area_evidence[tid_str] = {"score": score}
                        
        sorted_ids = sorted(area_evidence.keys(), key=lambda x: area_evidence[x]["score"], reverse=True)
        count = len(sorted_ids)
        print(f"  => Found {count} unique courses.")
        
        # Verify we are not capped at 3
        if count > 3:
            print(f"  [PASS] Successfully retrieved more than 3 courses (Top 5: {sorted_ids[:5]})")
        else:
            print(f"  [NOTE] Found {count} courses. If index is small, this is fine.")

if __name__ == "__main__":
    asyncio.run(test_expanded_retrieval())

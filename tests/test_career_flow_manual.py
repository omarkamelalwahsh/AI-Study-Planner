
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.skills import analyze_career_request
from app.utils.skill_index import find_skill_matches, load_index_into_memory

async def test_career_logic():
    print("--- 1. Testing Analysis ---")
    user_input = "how to become a god leader" # Intentional Typo
    print(f"Input: {user_input}")
    
    try:
        analysis = analyze_career_request(user_input)
        print(f"Analysis Result: {analysis}")
        print(f"Correction: {analysis.get('correction')}")
    except Exception as e:
        print(f"Analysis Failed/Scales (using Mock): {e}")
        analysis = {
            "target_role": "Good Leader",
            "correction": "I assume you meant 'Good Leader'",
            "skill_areas": [
                {"area_name": "Leadership", "search_keywords": ["Leadership", "Management"]},
                {"area_name": "Ghost Skills", "search_keywords": ["Ghosting"]} # Should result in 0 courses
            ]
        }
        print(f"Using Mock Analysis: {analysis}")

    print("\n--- 2. Testing Retrieval (Index Only) ---")
    skill_areas = analysis.get("skill_areas", [])
    
    # Init Index
    load_index_into_memory()

    # Iterate Areas
    for area in skill_areas:
        area_name = area.get("area_name")
        keywords = area.get("search_keywords", [])
        print(f"> Area: {area_name} (Keywords: {keywords})")
        
        found_ids = set()
        
        for kw in keywords:
            matches = find_skill_matches(kw)
            if matches:
                top = matches[0]
                c_ids = top.get('course_ids', [])
                if c_ids:
                    print(f"    -> Found {len(c_ids)} courses")
                    first_item = c_ids[0]
                    # Simulate Chat.py extraction logic
                    tid = first_item.get("course_id") if isinstance(first_item, dict) else first_item
                    print(f"    -> Sample extracted ID: {tid}")
                    
                    for c in c_ids: 
                        if isinstance(c, dict): found_ids.add(str(c))
                        else: found_ids.add(c)
                else:
                    print("    -> No courses in index for this key.")
            else:
                print(f"  - Keyword '{kw}' - No match in index.")
        
        count = len(found_ids)
        print(f"  => Total unique courses found for area '{area_name}': {count}")
        if count == 0:
            print(f"  [LOGIC CHECK] Area '{area_name}' SHOULD be dropped in Chat.py")
        else:
             print(f"  [LOGIC CHECK] Area '{area_name}' SHOULD be kept.")
            
    print("\n--- Test Complete ---")

if __name__ == "__main__":
    asyncio.run(test_career_logic())

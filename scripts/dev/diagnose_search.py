import sys
import os
import argparse
import pprint

# Add project root to path
sys.path.append(os.getcwd())

from app.search.router import SearchRouter

def diagnose(query: str):
    print(f"\n--- DIAGNOSING QUERY: '{query}' ---")
    try:
        response = SearchRouter.route_query(query)
        
        print(f"Intent Type: {response.get('intent_type')}")
        print(f"Reasoning:   {response.get('reasoning')}")
        print(f"Parsed Topic: {response.get('topic')}")
        print(f"Category:    {response.get('category')}")
        print(f"Level:       {response.get('level')}")
        
        status = response.get("status")
        print(f"Status:      {status}")
        
        if status == "no_match":
            print(f"Debug Reason: {response.get('debug_reason')}")
        
        # Count results
        total = 0
        for lvl, items in response.get("results_by_level", {}).items():
            count = len(items)
            total += count
            if count > 0:
                print(f"  [{lvl}]: {count} courses")
                # Print top 3
                for i, item in enumerate(items[:3]):
                    score = item.get("score", 0.0)
                    print(f"    {i+1}. {item['title']} (Score: {score:.3f})")
        
        print(f"Total Results: {total}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", help="Query string to test")
    parser.add_argument("--all", action="store_true", help="Run standard test suite")
    args = parser.parse_args()
    
    if args.query:
        diagnose(args.query)
    elif args.all:
        test_queries = [
            "Data Science",
            "AI",              # Synonym check
            "MySQL Kick Start", # Exact Title check (if exists) / or Topic
            "عاوز اتعلم sql",   # Topic
            "طبخ مكرونة",       # Arabic Out of Domain
            "Machine Learning Beginner",
            "Java for experts"
        ]
        for q in test_queries:
            diagnose(q)
    else:
        print("Usage: python scripts/diagnose_search.py '<query>' OR --all")

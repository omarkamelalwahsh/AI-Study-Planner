import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.search.router import SearchRouter
from app.search.relevance import extract_keywords, check_keyword_overlap, apply_strict_filters
from app.search.embedding import normalize_ar, expand_query
from app.search.retrieval import SearchEngine

def diagnose_query_v2(query):
    print(f"--- Diagnosing (V2): '{query}' ---")
    norm = normalize_ar(query)
    print(f"Normalized: {norm}")
    
    q_keywords = extract_keywords(norm)
    print(f"Keywords (unexpanded): {q_keywords}")
    
    expanded = expand_query(norm)
    print(f"Expanded: {expanded}")
    
    expanded_keywords = extract_keywords(expanded)
    print(f"Keywords (expanded): {expanded_keywords}")
    
    # 1. FAISS Search
    raw = SearchEngine.search(norm, top_k=5)
    print(f"Raw FAISS results: {len(raw)}")
    if raw:
        for i, c in enumerate(raw):
            print(f"  {i+1}. {c['title']} (Score: {c['score']:.4f})")
            content = f"{c.get('title', '')} {c.get('description', '')} {c.get('skills', '')}"
            
            # Check overlap logic
            # Current implementation uses whatever is passed to apply_strict_filters
            passed = check_keyword_overlap(q_keywords, content)
            print(f"     Overlap Check (unexpanded) -> {passed}")
            
            passed_ex = check_keyword_overlap(expanded_keywords, content)
            num_q = len(expanded_keywords)
            print(f"     Overlap Check (expanded, num_q={num_q}) -> {passed_ex}")

    # 2. Router Call
    response = SearchRouter.route_query(query)
    print(f"\nRouter Response:")
    print(f"  Status: {response['status']}")
    print(f"  Route: {response['route']}")
    print(f"  Message: {response['message']}")
    
    count = 0
    for lvl, items in response['results_by_level'].items():
        count += len(items)
    print(f"  Total Final Results: {count}")

if __name__ == "__main__":
    q = "عاوز اتعلم بايثون مازلت مبتدا"
    if len(sys.argv) > 1:
        q = sys.argv[1]
    diagnose_query_v2(q)

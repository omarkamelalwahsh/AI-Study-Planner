"""
Diagnostic script to test search score pipeline.
Tests the raw scores from SearchEngine.search to verify proper scoring.
"""
from app.search.retrieval import SearchEngine

# Test 1: Python query
print("=" * 60)
print("TEST 1: Query = 'python'")
print("=" * 60)
results = SearchEngine.search("python", top_k=10)
print(f"\nTop 10 raw results from SearchEngine.search:")
for i, r in enumerate(results[:10]):
    title = r.get('title', 'N/A')
    score = r.get('score', 0.0)
    print(f"{i+1}. {title[:50]:50s} | Score: {score:.4f}")

# Test 2: SQL query  
print("\n" + "=" * 60)
print("TEST 2: Query = 'sql'")
print("=" * 60)
results = SearchEngine.search("sql", top_k=10)
print(f"\nTop 10 raw results from SearchEngine.search:")
for i, r in enumerate(results[:10]):
    title = r.get('title', 'N/A')
    score = r.get('score', 0.0)
    print(f"{i+1}. {title[:50]:50s} | Score: {score:.4f}")

# Test 3: Check if scores are properly distributed
print("\n" + "=" * 60)
print("TEST 3: Score Distribution Analysis")
print("=" * 60)
results = SearchEngine.search("python", top_k=30)
if results:
    scores = [r.get('score', 0.0) for r in results]
    print(f"Total results: {len(results)}")
    print(f"Top score: {max(scores):.4f}")
    print(f"Min score: {min(scores):.4f}")
    print(f"Score range: {max(scores) - min(scores):.4f}")
    
    # Check band filtering
    top_score = scores[0]
    band = 0.04
    threshold = top_score - band
    within_band = [s for s in scores if s >= threshold]
    print(f"\nBand filtering (top - 0.04):")
    print(f"Threshold: {threshold:.4f}")
    print(f"Results within band: {len(within_band)}")
    print(f"Results outside band: {len(scores) - len(within_band)}")

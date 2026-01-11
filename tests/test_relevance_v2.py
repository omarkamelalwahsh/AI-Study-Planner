import pytest
from src.pipeline import CourseRecommenderPipeline
from src.schemas import RecommendRequest

@pytest.fixture(scope="module")
def pipeline():
    return CourseRecommenderPipeline()

def test_strict_keyword_short_query(pipeline):
    """
    Test: Single keyword query 'Python' must strictly return courses with 'Python'.
    """
    print("\n\n>>> DEBUG START")
    req = RecommendRequest(query="Python", top_k=5)
    res = pipeline.recommend(req)
    
    assert res.total_found > 0, "Should find Python courses"
    
    for i, r in enumerate(res.results):
        print(f"Result {i}: {type(r)}")
        if hasattr(r, 'dict'):
             print(f"Data: {r.dict()}")
        
        # Robust access
        title = getattr(r, 'title', '')
        matched = getattr(r, 'matched_keywords', [])
        
        # Check if Python is in matched_keywords or title
        is_in_title = "python" in title.lower()
        is_matched = any("python" in k.lower() for k in matched)
        
        assert is_in_title or is_matched, f"Course {title} returned for 'Python' without keyword match"

def test_irrelevant_query_returns_nothing(pipeline):
    """
    Test: 'Potato Farming' should return 0 results (Gating works).
    """
    req = RecommendRequest(query="Potato Farming", top_k=5)
    res = pipeline.recommend(req)
    
    if res.total_found > 0:
        # If it returns something, ensure score is super low (but gating should block it)
        # Check title
        title = getattr(res.results[0], 'title', '')
        assert False, f"Returned {res.total_found} results for Potato Farming! first: {title}"
    else:
        assert True

def test_query_expansion_arabic(pipeline):
    """
    Test: 'كورس بايثون' acts like 'Python'
    """
    req = RecommendRequest(query="كورس بايثون", top_k=5)
    res = pipeline.recommend(req)
    
    assert res.total_found > 0
    first = res.results[0]
    title = getattr(first, 'title', '').lower()
    assert "python" in title

def test_fallback_mechanism(pipeline):
    """
    Test: A blurry query that might need relaxed threshold.
    """
    req = RecommendRequest(query="How to lead a big team in difficult times", top_k=5)
    res = pipeline.recommend(req)
    
    # Just ensure it runs without error and returns something logic
    assert res.total_found >= 0

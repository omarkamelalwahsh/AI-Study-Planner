import pytest
from src.pipeline import CourseRecommenderPipeline
from src.schemas import RecommendRequest
import pytest

@pytest.fixture(scope="module")
def pipeline():
    return CourseRecommenderPipeline()

def test_strict_python_match(pipeline):
    """Query: 'Python' must return only courses mentioning Python"""
    req = RecommendRequest(query="Python", top_k=10)
    res = pipeline.recommend(req)
    
    assert res.total_found > 0
    for course in res.results:
        # Pydantic model access: course.title, course.debug_info
        content = f"{course.title} {course.debug_info.get('full_description', '')} {course.debug_info.get('skills', '')}".lower()
        assert "python" in content

def test_strict_flutter_match(pipeline):
    """Query: 'Flutter' must return no results if not in dataset."""
    req = RecommendRequest(query="Flutter", top_k=5)
    res = pipeline.recommend(req)
    
    if res.total_found == 0:
        assert len(res.results) == 0
    else:
        # If dataset updated to have Flutter, validation passes.
        # Check if contents match
        for course in res.results:
             content = f"{course.title} {course.debug_info.get('desc_snippet', '')}".lower()
             assert "flutter" in content

def test_missing_keyword_error(pipeline):
    """Query: 'Rust' (not in dataset) must return no results."""
    req = RecommendRequest(query="Rust programming language", top_k=5)
    res = pipeline.recommend(req)
    
    assert res.total_found == 0
    assert len(res.results) == 0

def test_abbreviation_expansion(pipeline):
    """Query: 'ML' must be expanded to 'machine learning'."""
    req = RecommendRequest(query="ML", top_k=5)
    res = pipeline.recommend(req)
    
    # Check debug info for normalized query
    assert "machine learning" in res.debug_info["normalized_query"]
    assert res.total_found > 0
    for course in res.results:
        content = f"{course.title} {course.debug_info.get('full_description', '')} {course.debug_info.get('skills', '')}".lower()
        assert "machine" in content or "learning" in content or "ml" in content

def test_rank_range(pipeline):
    """Rank must be 1-10 int."""
    req = RecommendRequest(query="Python", top_k=5)
    res = pipeline.recommend(req)
    
    if res.results:
        for r in res.results:
            assert isinstance(r.rank, int)
            assert 1 <= r.rank <= 10

def test_arabic_query(pipeline):
    """Arabic query 'كورس بايثون' should find English Python courses."""
    req = RecommendRequest(query="كورس بايثون", top_k=5)
    res = pipeline.recommend(req)
    
    assert res.total_found > 0
    for r in res.results:
        content = f"{r.title} {r.debug_info.get('full_description', '')} {r.debug_info.get('skills', '')}".lower()
        assert "python" in content

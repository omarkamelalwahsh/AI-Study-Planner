import pytest
from unittest.mock import MagicMock, patch
from app.search.router import SearchRouter
from app.search.relevance import apply_strict_filters, is_generic_query, extract_keywords
from app.models import Course

# -------------------------------
# Unit Tests for Logic/Guards
# -------------------------------

def test_generic_queries():
    """Test G) Scenarios: Generic guards"""
    assert is_generic_query("Is this a good course?") == True
    assert is_generic_query("recommend") == True
    assert is_generic_query("recommend java") == False # Has subject 'java'
    assert is_generic_query("تنصح؟") == True
    assert is_generic_query("كورس كويس؟") == True
    assert is_generic_query("good SQL course") == False
    assert is_generic_query("python") == False

def test_keyword_extraction_and_business_fundamentals():
    """Test G) 'Business Fundamentals' should ignore 'fundamentals'"""
    keywords = extract_keywords("Business Fundamentals")
    # fundamentals is in STOPWORDS/GENERIC (checked in embedding.py)
    assert "fundamentals" not in keywords
    assert "business" in keywords

# -------------------------------
# Integration-like Tests with Mocks
# -------------------------------

@pytest.fixture
def mock_db():
    with patch("app.search.router.SessionLocal") as mock:
        session = MagicMock()
        mock.return_value = session
        yield session

@pytest.fixture
def mock_search_engine():
    with patch("app.search.router.SearchEngine") as mock:
        yield mock

def test_title_route_match(mock_db, mock_search_engine):
    """Test H) '03 D Max...' -> Title Route"""
    # Create a simple course-like object instead of MagicMock for data fields
    class CourseStub:
        def __init__(self, **kwargs):
            for k, v in kwargs.items(): setattr(self, k, v)
    
    stub_course = CourseStub(
        id=1,
        title="03 D Max Start Creating your Own Project Material",
        category="3D Design",
        level="Intermediate",
        description="3D modeling",
        skills="3ds max",
        score=1.0
    )
    
    # Mock all courses list for the fuzzy matcher
    mock_db.query.return_value.all.return_value = [stub_course]
    
    # Mock specific filter for return
    mock_db.query.return_value.filter.return_value.all.return_value = [stub_course]
    
    response = SearchRouter.route_query("03 D Max")
    
    assert response["status"] == "ok"
    assert response["route"] == "title"
    assert "Intermediate" in response["results_by_level"]
    assert len(response["results_by_level"]["Intermediate"]) == 1

def test_category_route_match(mock_db, mock_search_engine):
    """Test Category Route"""
    class CourseStub:
        def __init__(self, **kwargs):
            for k, v in kwargs.items(): setattr(self, k, v)
            
    stub_course = CourseStub(
        id=1,
        title="Some Course",
        category="Web Development",
        level="Beginner",
        score=1.0,
        description="web dev",
        skills="html"
    )
    
    # Mock all courses list
    mock_db.query.return_value.all.return_value = [stub_course]
    
    # Mock filtered query
    mock_db.query.return_value.filter.return_value.all.return_value = [stub_course]
    
    response = SearchRouter.route_query("Web Development")
    
    assert response["status"] == "ok"
    assert response["route"] == "category"
    assert len(response["results_by_level"]["Beginner"]) == 1

def test_semantic_route_success(mock_db, mock_search_engine):
    """Test 'recommend java' -> Semantic Route Success"""
    # Mock all courses (no title/category match)
    mock_db.query.return_value.all.return_value = []
    
    # Mock SearchEngine
    mock_search_engine.search.return_value = [
        {"id": "1", "title": "Java Masterclass", "description": "Learn Java", "score": 0.9, "level": "Beginner", "skills": "Java"}
    ]
    
    response = SearchRouter.route_query("recommend java")
    
    assert response["status"] == "ok"
    assert response["route"] == "semantic"
    assert len(response["results_by_level"]["Beginner"]) == 1

def test_band_filter_enforcement(mock_db, mock_search_engine):
    """Test H) Band Filter: score >= max(0.78, top_score - 0.04)"""
    mock_db.query.return_value.all.return_value = []
    
    # Case 1: High top score (0.9)
    # Threshold = 0.9 - 0.04 = 0.86
    mock_search_engine.search.return_value = [
        {"id": "1", "title": "Python Top", "score": 0.9, "level": "Beginner", "description": "python"},
        {"id": "2", "title": "Python Mid", "score": 0.87, "level": "Beginner", "description": "python"},
        {"id": "3", "title": "Python Low", "score": 0.85, "level": "Beginner", "description": "python"}
    ]
    
    response = SearchRouter.route_query("python")
    results = []
    for lvl in response["results_by_level"].values(): results.extend(lvl)
    
    assert len(results) == 2 # 0.9 and 0.87 should pass, 0.85 fails
    
    # Case 2: Low top score (0.80)
    # Threshold = max(0.80 - 0.04, 0.78) = 0.78
    mock_search_engine.search.return_value = [
        {"id": "1", "title": "Python Top", "score": 0.80, "level": "Beginner", "description": "python"},
        {"id": "2", "title": "Python Mid", "score": 0.79, "level": "Beginner", "description": "python"},
        {"id": "3", "title": "Python Low", "score": 0.77, "level": "Beginner", "description": "python"}
    ]
    
    response = SearchRouter.route_query("python")
    results = []
    for lvl in response["results_by_level"].values(): results.extend(lvl)
    
    assert len(results) == 2 # 0.80 and 0.79 should pass, 0.77 fails

def test_keyword_overlap_strict(mock_db, mock_search_engine):
    """Test Keyword Overlap: CSS should not show irrelevant results"""
    mock_db.query.return_value.all.return_value = []
    
    mock_search_engine.search.return_value = [
        {"id": "1", "title": "Advanced CSS", "score": 0.9, "level": "Advanced", "description": "css styling"},
        {"id": "2", "title": "HTML Basics", "score": 0.88, "level": "Beginner", "description": "html layout"}, # No 'css' word
    ]
    
    response = SearchRouter.route_query("css")
    results = []
    for lvl in response["results_by_level"].values(): results.extend(lvl)
    
    assert len(results) == 1
    assert results[0]["title"] == "Advanced CSS"

def test_level_fallback(mock_db, mock_search_engine):
    """Test D) Level fallback if result is 0"""
    mock_db.query.return_value.all.return_value = []
    
    # Mock SearchEngine results (Only Beginner courses)
    mock_search_engine.search.return_value = [
        {"id": "1", "title": "SQL Basics", "description": "Basics", "score": 0.9, "level": "Beginner", "skills": "SQL"}
    ]
    
    # Query with explicit advanced level
    response = SearchRouter.route_query("sql محترف") 
    
    assert response["status"] == "ok"
    assert response["level_mode"] == "fallback_all_levels"
    assert len(response["results_by_level"]["Beginner"]) == 1
    assert "لم نجد نتائج للمستوى Advanced" in response["message"]

def test_blocked_generic_query(mock_db):
    """Test E) Blocked opinion queries"""
    response = SearchRouter.route_query("recommend")
    assert response["status"] == "no_match"
    assert response["debug_reason"] in ["generic_no_subject", "opinion_no_subject"]
    
    response = SearchRouter.route_query("Is this a good course?")
    assert response["status"] == "no_match"
def test_level_up_filtering(mock_db, mock_search_engine):
    """Test Phase 7: Level-Up Logic - Specified level + higher ones"""
    mock_db.query.return_value.all.return_value = []
    
    # 1. Mock search results with all levels
    mock_search_engine.search.return_value = [
        {"id": "1", "title": "Py Beginner", "score": 0.9, "level": "Beginner", "description": "python"},
        {"id": "2", "title": "Py Mid", "score": 0.85, "level": "Intermediate", "description": "python"},
        {"id": "3", "title": "Py Advanced", "score": 0.8, "level": "Advanced", "description": "python"}
    ]
    
    # CASE A: Request "Intermediate"
    # Should show Intermediate and Advanced, but NOT Beginner
    response = SearchRouter.route_query("python متوسط")
    assert response["status"] == "ok"
    assert "Py Mid" in [r["title"] for r in response["results_by_level"]["Intermediate"]]
    assert "Py Advanced" in [r["title"] for r in response["results_by_level"]["Advanced"]]
    assert len(response["results_by_level"]["Beginner"]) == 0
    assert response["level_mode"] == "level_filtered"

    # CASE B: Request "Beginner"
    # Should show all three
    response = SearchRouter.route_query("python مبتدئ")
    assert response["status"] == "ok"
    assert len(response["results_by_level"]["Beginner"]) == 1
    assert len(response["results_by_level"]["Intermediate"]) == 1
    assert len(response["results_by_level"]["Advanced"]) == 1
    
    # CASE C: Request "Advanced"
    # Should show only Advanced
    response = SearchRouter.route_query("python محترف")
    assert response["status"] == "ok"
    assert len(response["results_by_level"]["Beginner"]) == 0
    assert len(response["results_by_level"]["Intermediate"]) == 0
    assert len(response["results_by_level"]["Advanced"]) == 1

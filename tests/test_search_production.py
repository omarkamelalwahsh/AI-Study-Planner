import pytest
from unittest.mock import MagicMock, patch
from app.search.router import SearchRouter, INTENT_CATEGORY, INTENT_EXACT_COURSE, INTENT_TOPIC, INTENT_NO_MATCH
from app.models import Course

# Mock DB Data
MOCK_COURSES = [
    Course(id=1, title="Data Science for Beginners", category="Data Science", level="Beginner", description="Intro to DS", skills="Python, SQL"),
    Course(id=2, title="Advanced Machine Learning", category="Data Science", level="Advanced", description="Deep Learning", skills="PyTorch, TensorFlow"),
    Course(id=3, title="Introduction to MySQL", category="Database", level="Beginner", description="Learn SQL", skills="SQL, MySQL"),
    Course(id=4, title="Python Web Development", category="Web Development", level="Intermediate", description="Django and Flask", skills="Python, Django"),
]

@pytest.fixture
def mock_db_session():
    with patch("app.search.router.SessionLocal") as mock_session_cls:
        session = MagicMock()
        mock_session_cls.return_value = session
        
        # Setup mock queries
        # 1. Categories
        mock_cat_query = MagicMock()
        mock_cat_query.distinct.return_value.all.return_value = [("Data Science",), ("Database",), ("Web Development",)]
        
        # 2. Titles
        mock_title_query = MagicMock()
        mock_title_query.all.return_value = [("Data Science for Beginners",), ("Advanced Machine Learning",), ("Introduction to MySQL",), ("Python Web Development",)]
        
        # Determine what to return based on filter calls is hard with simple Mocks
        # So we will use a side_effect for the main Course query
        
        def filter_side_effect(*args, **kwargs):
            # This is complex to mock accurately for SQLAlchemy filter expressions
            # We will try to mock the result of .all() based on the last call context if possible,
            # or just return all mock courses and let the router filter (but router relies on DB filtering).
            # Instead of mocking exact DB behavior, let's mock SearchRouter._return_category etc internal calls?
            # No, we want to test the routing logic.
            # We can mock the `db.query(Course).filter(...).all()` chain.
            return MagicMock()

        # Simplification: We will integration test logic units or mock specifically for each test case
        # But for "Router Rules", we can mock the `parse_query_basic` or `SearchEngine.search` mostly.
        
        yield session

def test_category_query_exact():
    with patch("app.search.router.SessionLocal") as mock_session_cls:
        session = mock_session_cls.return_value
        
        # Setup Category return
        session.query.return_value.distinct.return_value.all.return_value = [("Data Science",), ("Web Development",)]
        
        # When we query for courses in category, return specific list
        # We assume the Router does: db.query(Course).filter(Course.category == cat).all()
        # We can't easily mock the filter condition match, so we rely on the Router calling it.
        
        courses_mock = [MOCK_COURSES[0], MOCK_COURSES[1]]
        # Mock the chain: session.query(Course).filter(...).all() -> courses_mock
        # This is brittle. Better to trust the Logic of "Router identifies intent".
        
        response = SearchRouter.route_query("Data Science")
        assert response["intent_type"] == INTENT_CATEGORY
        assert response["category"] == "Data Science"

def test_category_synonym():
    # "AI" -> Synomym to "Data Science" (if configured in manual map)
    # manual_synonyms = {"data science": ["ai", ...]}
    with patch("app.search.router.SessionLocal") as mock_session_cls:
        session = mock_session_cls.return_value
        session.query.return_value.distinct.return_value.all.return_value = [("Data Science",)]
        
        response = SearchRouter.route_query("AI")
        # Should match Data Science via synonym
        assert response["intent_type"] == INTENT_CATEGORY
        assert response["category"] == "Data Science"

def test_exact_course_match():
    with patch("app.search.router.SessionLocal") as mock_session_cls:
        session = mock_session_cls.return_value
        # Categories
        session.query.return_value.distinct.return_value.all.return_value = [("Data Science",)]
        # Titles
        session.query.return_value.all.return_value = [("Introduction to MySQL",)]
        
        # Mock specific course return
        mock_course = MOCK_COURSES[2] # Intro to MySQL
        session.query.return_value.filter.return_value.first.return_value = mock_course
        
        # Mock SearchEngine.search for related
        with patch("app.search.router.SearchEngine.search") as mock_search:
            mock_search.return_value = [] # no related for this test
            
            response = SearchRouter.route_query("Introduction to MySQL")
            assert response["intent_type"] == INTENT_EXACT_COURSE
            assert response["search_text"] == "Introduction to MySQL"
            assert response["results_by_level"]["Beginner"][0]["id"] == str(mock_course.id)

def test_topic_search_arabic_out_of_domain():
    with patch("app.search.router.SessionLocal") as mock_session_cls:
        session = mock_session_cls.return_value
        # No cats/titles match
        session.query.return_value.distinct.return_value.all.return_value = []
        session.query.return_value.all.return_value = []
        
        # Query "طبخ مكرونة" (Cooking Pasta) -> Arabic only, no latin
        response = SearchRouter.route_query("طبخ مكرونة")
        assert response["intent_type"] == INTENT_NO_MATCH
        assert "arabic_only_out_of_domain" in response.get("debug_reason", "")

def test_topic_search_valid():
    with patch("app.search.router.SessionLocal") as mock_session_cls:
        session = mock_session_cls.return_value
        session.query.return_value.distinct.return_value.all.return_value = []
        session.query.return_value.all.return_value = []
        
        # Mock Vector Search
        with patch("app.search.router.SearchEngine.search") as mock_search:
            # Return good matches
            mock_search.return_value = [
                {"id": "1", "title": "Learn SQL", "category": "Database", "score": 0.85, "level": "Beginner"}
            ]
            
            response = SearchRouter.route_query("SQL")
            assert response["intent_type"] == INTENT_TOPIC
            assert len(response["results_by_level"]["Beginner"]) > 0

def test_topic_search_low_score_gate():
    with patch("app.search.router.SessionLocal") as mock_session_cls:
        session = mock_session_cls.return_value
        session.query.return_value.distinct.return_value.all.return_value = []
        session.query.return_value.all.return_value = []
        
        # Mock Vector Search with LOW score (below 0.60)
        with patch("app.search.router.SearchEngine.search") as mock_search:
            mock_search.return_value = [
                {"id": "99", "title": "Irrelevant", "category": "Other", "score": 0.40, "level": "Beginner"}
            ]
            
            response = SearchRouter.route_query("Some weird generic topic")
            assert response["intent_type"] == INTENT_NO_MATCH
            assert "low_similarity_threshold" in response.get("debug_reason", "")

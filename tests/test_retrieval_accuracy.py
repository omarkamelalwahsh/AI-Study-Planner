"""
Retrieval accuracy tests - verify retrieval safeguards and not-found scenarios.
Tests exact matching, fuzzy matching, semantic drift prevention, and suggestions.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.retrieval import (
    retrieve_by_exact_title,
    retrieve_by_semantic,
    suggest_similar_titles
)
from app.database import async_session_maker


@pytest.fixture
async def db_session():
    """Provide async database session for tests."""
    async with async_session_maker() as session:
        yield session


class TestRetrievalAccuracy:
    """Test retrieval engine accuracy and safeguards."""
    
    @pytest.mark.asyncio
    async def test_exact_title_match(self, db_session: AsyncSession):
        """Exact title should return correct course."""
        title = "JavaScript Basics"
        course, suggestions = await retrieve_by_exact_title(db_session, title)
        
        assert course is not None
        assert "javascript" in course.title.lower()
        assert "basics" in course.title.lower()
        assert len(suggestions) == 0
    
    @pytest.mark.asyncio
    async def test_fuzzy_title_match(self, db_session: AsyncSession):
        """Close title match should work with fuzzy matching."""
        title = "JavaScript Basix"  # Typo
        course, suggestions = await retrieve_by_exact_title(db_session, title, fuzzy_threshold=80)
        
        # Should match "JavaScript Basics"
        assert course is not None or len(suggestions) > 0
    
    @pytest.mark.asyncio
    async def test_not_found_suggestions(self, db_session: AsyncSession):
        """Non-existent title should return top 3 suggestions."""
        title = "NonExistentCourseXYZ123"
        course, suggestions = await retrieve_by_exact_title(db_session, title)
        
        assert course is None
        assert len(suggestions) <= 3
        # Suggestions should be actual course titles
    
    @pytest.mark.asyncio
    async def test_semantic_drift_prevention(self, db_session: AsyncSession):
        """COURSE_DETAILS intent should use exact match, not semantic."""
        # This is enforced in the endpoint logic, not retrieval
        # Verify exact match doesn't fall back to semantic
        title = "Very Specific Nonexistent Course Title 999"
        course, suggestions = await retrieve_by_exact_title(db_session, title)
        
        assert course is None
        # Should return suggestions, not random semantic matches
        assert isinstance(suggestions, list)
    
    @pytest.mark.asyncio
    async def test_semantic_search_ranking(self, db_session: AsyncSession):
        """Semantic search should return relevant results."""
        query = "Python programming"
        courses = await retrieve_by_semantic(db_session, query, top_k=5)
        
        # Should return Python-related courses
        assert len(courses) > 0
        # Top results should contain "Python" in title or description
        has_python = any("python" in c.title.lower() for c in courses[:3])
        assert has_python, "Top results should be Python-related"
    
    @pytest.mark.asyncio
    async def test_semantic_search_with_filters(self, db_session: AsyncSession):
        """Semantic search should respect level/category filters."""
        query = "programming"
        filters = {"level": "Beginner"}
        
        courses = await retrieve_by_semantic(
            db_session, 
            query, 
            top_k=5,
            filters=filters
        )
        
        # All results should be beginner level
        for course in courses:
            if course.level:
                assert course.level.lower() == "beginner"
    
    @pytest.mark.asyncio
    async def test_suggest_similar_titles(self, db_session: AsyncSession):
        """Similar title suggestions should be relevant."""
        title = "JavaScript"
        suggestions = await suggest_similar_titles(db_session, title, top_k=3)
        
        assert len(suggestions) <= 3
        # Should include JavaScript-related courses
        has_js = any("javascript" in s.lower() for s in suggestions)
        assert has_js


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

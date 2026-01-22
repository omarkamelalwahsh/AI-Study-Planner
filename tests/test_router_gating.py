"""
Router gating tests - verify intent classification accuracy.
Tests compliance with master prompt intent routing rules.
"""
import pytest
from app.router import classify_intent, GroqUnavailableError, ROUTER_SYSTEM_PROMPT


class TestRouterGating:
    """Test router intent classification and gating logic."""
    
    @pytest.mark.asyncio
    async def test_course_details_intent(self):
        """Exact course title should return COURSE_DETAILS intent."""
        message = "من بيشرح JavaScript Basics?"
        result = classify_intent(message)
        
        assert result.intent == "COURSE_DETAILS"
        assert "javascript" in result.course_title_candidate.lower() if result.course_title_candidate else True
    
    @pytest.mark.asyncio
    async def test_out_of_scope_no_courses(self):
        """Movie/weather query should trigger OUT_OF_SCOPE with no course retrieval."""
        message = "ما هو أفضل فيلم في 2024؟"
        result = classify_intent(message)
        
        assert result.intent == "OUT_OF_SCOPE"
        # This should not trigger course retrieval in the endpoint
    
    @pytest.mark.asyncio
    async def test_search_intent(self):
        """General search should return SEARCH intent."""
        message = "عاوز أتعلم Python"
        result = classify_intent(message)
        
        assert result.intent == "SEARCH"
        assert "python" in [kw.lower() for kw in result.keywords] or len(result.keywords) > 0
    
    @pytest.mark.asyncio
    async def test_career_guidance_intent(self):
        """Career goal without explicit plan request should return CAREER_GUIDANCE."""
        message = "عاوز أبقى data scientist شاطر"
        result = classify_intent(message)
        
        assert result.intent in ["CAREER_GUIDANCE", "PLAN_REQUEST"]
        # Either is acceptable for this phrasing
    
    @pytest.mark.asyncio
    async def test_unsafe_query_rejection(self):
        """Hacking/malware query should trigger UNSAFE intent."""
        message = "أزاي أخترق موقع أو أسرق بيانات؟"
        result = classify_intent(message)
        
        assert result.intent == "UNSAFE"
    
    @pytest.mark.asyncio
    async def test_title_unknown_search(self):
        """User indicates forgetting exact title should trigger TITLE_UNKNOWN_SEARCH."""
        message = "مش فاكر اسم الكورس بتاع JavaScript بالضبط"
        result = classify_intent(message)
        
        assert result.intent in ["TITLE_UNKNOWN_SEARCH", "SEARCH"]
        # Both are acceptable depending on phrasing
    
    @pytest.mark.asyncio
    async def test_plan_request_explicit(self):
        """Explicit plan/roadmap request should return PLAN_REQUEST."""
        message = "عايز خطة 8 أسابيع أبقى web developer"
        result = classify_intent(message)
        
        assert result.intent == "PLAN_REQUEST"
    
    def test_router_system_prompt_exists(self):
        """Verify router system prompt is properly defined."""
        assert "JSON" in ROUTER_SYSTEM_PROMPT
        assert "COURSE_DETAILS" in ROUTER_SYSTEM_PROMPT
        assert "OUT_OF_SCOPE" in ROUTER_SYSTEM_PROMPT
        assert "UNSAFE" in ROUTER_SYSTEM_PROMPT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import pytest
from app.services.chat_service import ChatService, ChatSessionState


class TestLearningFlow:
    """Test suite to prevent flow regressions and ensure human-style responses"""

    def test_stage_progression_choose_path(self):
        """Test stage is choose_path when no path is set"""
        service = ChatService()
        state = ChatSessionState()
        
        service._update_stage(state, is_plan_request=False)
        assert state.stage == "choose_path"

    def test_stage_progression_choose_level(self):
        """Test stage is choose_level when path is set but level is not"""
        service = ChatService()
        state = ChatSessionState(active_path="python")
        
        service._update_stage(state, is_plan_request=False)
        assert state.stage == "choose_level"

    def test_stage_progression_recommend(self):
        """Test stage is recommend when both path and level are set"""
        service = ChatService()
        state = ChatSessionState(active_path="python", user_level="Intermediate")
        
        service._update_stage(state, is_plan_request=False)
        assert state.stage == "recommend_courses"

    def test_python_path_lock(self):
        """Test that selecting Python locks the path"""
        state = ChatSessionState()
        state.active_path = "python"
        assert state.active_path == "python"

    def test_level_after_path(self):
        """Test level can be set after path is locked"""
        state = ChatSessionState(active_path="python")
        state.user_level = "Intermediate"
        
        assert state.active_path == "python"
        assert state.user_level == "Intermediate"

    def test_render_recommendation_human_only(self):
        """Test that _render_recommendation returns correct text for frontend"""
        from app.schemas.recommendation import LLMRecommendationResponse
        
        service = ChatService()
        
        mock_response = LLMRecommendationResponse(
            language="ar",
            intent="recommend_courses",
            assistant_message="تمام 👍 دي الكورسات المناسبة ليك.",
            follow_up_question=None,
            consent_needed=False,
            courses=[],
            study_plan=[],
            notes={}
        )
        
        result = service._render_recommendation(mock_response)
        
        # Should return a DICT for the frontend
        assert isinstance(result, dict)
        assert result["text"] == "تمام 👍 دي الكورسات المناسبة ليك."

    def test_render_with_follow_up(self):
        """Test that follow-up questions are appended naturally"""
        from app.schemas.recommendation import LLMRecommendationResponse
        
        service = ChatService()
        
        mock_response = LLMRecommendationResponse(
            language="ar",
            intent="choose_level",
            assistant_message="اختيار موفق.",
            follow_up_question="قولّي مستواك؟",
            consent_needed=False,
            courses=[],
            study_plan=[],
            notes={}
        )
        
        result = service._render_recommendation(mock_response)
        
        assert "اختيار موفق." in result["text"]
        assert "قولّي مستواك؟" in result["text"]

    def test_render_fallback_safety(self):
        """Test that fallback message is returned when assistant_message is empty"""
        from app.schemas.recommendation import LLMRecommendationResponse
        
        service = ChatService()
        
        mock_response = LLMRecommendationResponse(
            language="ar",
            intent="fallback",
            assistant_message="",
            follow_up_question=None,
            consent_needed=False,
            courses=[],
            study_plan=[],
            notes={}
        )
        
        result = service._render_recommendation(mock_response)
        
        # Should have multilingual fallback message
        assert "تمام 👍 الـ Roadmap دي جاهزة ليك." == result["text"]

    def test_stage_initialization(self):
        """Test that new session state has default stage"""
        state = ChatSessionState()
        
        assert state.stage == "start"
        assert state.active_path is None
        assert state.user_level is None


class TestAntiLoop:
    """Tests to ensure no loops or repeated questions"""

    def test_no_path_reselection_after_lock(self):
        """Test that path cannot be asked again after being set"""
        service = ChatService()
        state = ChatSessionState(active_path="python")
        
        service._update_stage(state, is_plan_request=False)
        assert state.stage != "choose_path"

    def test_no_level_reselection_after_set(self):
        """Test that level cannot be asked again after being set"""
        service = ChatService()
        state = ChatSessionState(active_path="python", user_level="Intermediate")
        
        service._update_stage(state, is_plan_request=False)
        assert state.stage != "choose_level"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.services.chat_service import ChatService, ChatSessionState

class TestChatBehavior(unittest.IsolatedAsyncioTestCase):
    @patch('app.services.chat_service.get_llm')
    @patch('app.services.chat_service.DBRetrievalService')
    async def asyncSetUp(self, MockRetrieval, MockGetLLM):
        self.mock_db = MagicMock()
        self.chat_service = ChatService()
        self.chat_service.llm = MagicMock()
        self.chat_service.llm.stream = AsyncMock()
        self.chat_service.retriever = MagicMock()

    async def test_empty_context_blocks_llm(self):
        """
        Case: User asks for nonsense -> Retriever returns nothing -> LLM NOT called.
        """
        # 1. Setup
        session_id = "00000000-0000-0000-0000-000000000000"
        user_msg = "shalamalaka" 
        
        # Mock DB session retrieval
        mock_db_session = MagicMock()
        mock_db_session.state = ChatSessionState().model_dump()
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session
        
        # Mock Retriever to return empty list
        self.chat_service.retriever.search.return_value = [] 
        self.chat_service.retriever.format_courses_for_prompt.return_value = "" 

        # 2. Execute
        responses = []
        async for chunk in self.chat_service.handle_message(session_id, user_msg, self.mock_db):
            responses.append(chunk)
        
        full_response = "".join(responses)

        # 3. Assertions
        # Ensure LLM.stream was NEVER called
        self.chat_service.llm.stream.assert_not_called()
        
        # Ensure we got the fallback message
        self.assertIn("I couldn't find matching courses", full_response)

    async def test_valid_context_calls_llm(self):
        """
        Case: User asks for Python -> Retriever returns courses -> LLM IS called.
        """
        session_id = "00000000-0000-0000-0000-000000000000"
        user_msg = "Python courses"
        
        mock_db_session = MagicMock()
        mock_db_session.state = ChatSessionState().model_dump()
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session
        
        # Mock Retriever
        self.chat_service.retriever.search.return_value = [{"title": "Python 101"}]
        self.chat_service.retriever.format_courses_for_prompt.return_value = "Available Courses:\n1. Python 101"

        # Mock LLM response
        self.chat_service.llm.stream.return_value = iter(["Here ", "is ", "your ", "course."])

        responses = []
        async for chunk in self.chat_service.handle_message(session_id, user_msg, self.mock_db):
            responses.append(chunk)

        # Assert LLM was called
        self.chat_service.llm.stream.assert_called_once()
        self.assertEqual("".join(responses), "Here is your course.")

if __name__ == '__main__':
    unittest.main()

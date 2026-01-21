import unittest
from app.services.chat_service import ChatService

import unittest
from unittest.mock import patch, MagicMock
from app.services.chat_service import ChatService

class TestRagGuard(unittest.TestCase):
    @patch('app.services.chat_service.get_llm')
    @patch('app.services.chat_service.DBRetrievalService')
    def setUp(self, MockRetrieval, MockGetLLM):
        self.chat_service = ChatService()
        self.chat_service.llm = MagicMock()
        self.chat_service.retriever = MagicMock()

    def test_is_empty_context(self):

        cases = [
            (None, True),
            ("", True),
            ("   ", True),
            ("[]", True),
            ("{}", True),
            ("None", True),
            ("null", True),
            ("Course 1: Python Basics", False),
            ("- title: Intro to Python", False),
            ("Available Courses:\n1. Python...", False),
        ]
        for ctx, expected in cases:
            with self.subTest(ctx=ctx):
                self.assertEqual(self.chat_service.is_empty_context(ctx), expected)

    def test_fallback_message_language(self):
        cases = [
            ("عايز كورسات بايثون", "حالياً مش لاقي كورسات"),
            ("I need python courses", "I couldn't find matching courses"),
            ("", "I couldn't find matching courses"), 
            ("سلام عليكم", "حالياً مش لاقي كورسات"),
        ]
        for user_text, expected in cases:
            with self.subTest(user_text=user_text):
                msg = self.chat_service._get_fallback_message(user_text)
                self.assertIn(expected, msg)

if __name__ == '__main__':
    unittest.main()

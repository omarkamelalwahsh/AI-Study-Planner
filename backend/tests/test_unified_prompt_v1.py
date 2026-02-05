"""
Unified Prompt v1.0 Verification Tests
Refined for: Simplified Exploration (Skip sub-tracks), No Looping, Strict Language Lock.
Run with: python -m unittest backend/tests/test_unified_prompt_v1.py
"""
import unittest
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import chat
from models import ChatRequest, IntentType
from data_loader import data_loader

class TestUnifiedPromptV1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n[UNIFIED V1.0] Loading Data...")
        data_loader.load_all()

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _chat(self, msg: str, sid: str = "v1_test"):
        return await chat(ChatRequest(message=msg, session_id=sid))

    def test_language_lock_arabic(self):
        """Rule 1: Arabic query -> Arabic response even for English words."""
        print("\n[UNIFIED V1.0] Testing Language Lock (Arabic)...")
        res = self._run_async(self._chat("عاوز اتعلم Web Design"))
        
        has_arabic = any("\u0600" <= c <= "\u06FF" for c in res.answer)
        self.assertTrue(has_arabic, f"Response should be in Arabic: {res.answer}")
        self.assertEqual(res.language, "ar")

    def test_exploration_flow_immediate_domains(self):
        """Rule: Exploration Step 1 -> Show Domains."""
        print("\n[UNIFIED V1.0] Testing Exploration Flow Step 1...")
        res = self._run_async(self._chat("مش عارف أبدأ منين"))
        
        self.assertEqual(res.intent, IntentType.EXPLORATION)
        self.assertIsNotNone(res.ask)
        self.assertIn("Programming", res.ask.choices)

    def test_domain_pick_handoff_to_courses(self):
        """Rule: Picking a domain -> Immediate COURSE_SEARCH (Skip sub-tracks)."""
        print("\n[UNIFIED V1.0] Testing Domain Pick Handoff...")
        # Select "Programming" domain
        res = self._run_async(self._chat("Programming", sid="exploration_handoff"))
        
        # Should be COURSE_SEARCH now
        self.assertEqual(res.intent, IntentType.COURSE_SEARCH)
        self.assertTrue(len(res.courses) > 0, "Should return courses for the picked domain")
        self.assertTrue(len(res.courses) <= 3, "Should show top 3 only")

    def test_learning_path_slot_filling(self):
        """Rule D: Missing slots -> Ask with specific choices."""
        print("\n[UNIFIED V1.0] Testing Learning Path Slot Filling...")
        res = self._run_async(self._chat("عاوز خطة مذاكرة بايثون"))
        
        self.assertEqual(res.intent, IntentType.LEARNING_PATH)
        self.assertIsNotNone(res.ask)
        # Check for duration or daily time choices
        valid_choices = ["أسبوع", "أسبوعين", "شهر", "شهرين", "ساعة", "ساعتين", "3+"]
        self.assertTrue(any(c in valid_choices for c in res.ask.choices))

    def test_no_looping_unsure(self):
        """Rule 3: Never repeat same question/choices thrice."""
        print("\n[UNIFIED V1.0] Testing No Looping (Unsure)...")
        sid = "loop_test"
        # Turn 1: Unsure
        res1 = self._run_async(self._chat("مش عارف", sid=sid))
        q1 = res1.ask.question if res1.ask else None
        
        # Turn 2: Unsure again
        res2 = self._run_async(self._chat("مش عارف", sid=sid))
        q2 = res2.ask.question if res2.ask else None
        
        # Turn 3: Unsure again -> Should STOP or change response
        res3 = self._run_async(self._chat("مش عارف", sid=sid))
        q3 = res3.ask.question if res3.ask else None
        
        print(f"   -> Q1: {q1}")
        print(f"   -> Q2: {q2}")
        print(f"   -> Q3: {q3}")
        
        # Either the question changed or it stopped asking (null)
        self.assertTrue(q1 != q3 or q3 is None, "Should not loop the same question 3 times")

if __name__ == '__main__':
    unittest.main()

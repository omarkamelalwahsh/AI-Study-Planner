"""
V19 Final Production Tests (The 'Production 5')
Strict tests for: Hallucination Block, Role/Skill Discipline, UX Determinism.
Run with: python -m pytest backend/tests/test_v19_final.py -v
"""
import unittest
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import chat
from models import ChatRequest, IntentType
from data_loader import data_loader
from pipeline.response_builder import ResponseBuilder
from pipeline.intent_router import IntentRouter

class TestV19Final(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        print("\n[V19 FINAL TESTS] Loading Data...")
        data_loader.load_all()

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _chat(self, msg: str, sid: str = "v19_final"):
        return await chat(ChatRequest(message=msg, session_id=sid))

    # TEST 1: Out-of-Catalog Honesty
    # "Blockchain" -> Must say unavailable + 0 interpolated courses
    def test_out_of_catalog_blockchain(self):
        print("\n[V19] 1. Testing Out-of-Catalog Honesty (Blockchain)...")
        res = self._run_async(self._chat("Blockchain Engineering courses"))
        
        # 1. Answer must admit absence
        print(f"   -> Answer: {res.answer[:100]}...")
        self.assertTrue("not currently available" in res.answer or "unavailable" in res.answer or "غير متوفر" in res.answer or "don't have" in res.answer, "Failed to admit absence!")
        
        # 2. ZERO Hallucinated Courses
        curr_len = len(res.courses)
        print(f"   -> Returned Courses: {curr_len}")
        self.assertEqual(curr_len, 0, f"HALLUCINATION DETECTED! Expected 0 courses, got {curr_len}")

    # TEST 2: Role Correctness
    # "Junior Dev -> Data Engineer" -> Must recommend SQL/ETL, NOT Django
    def test_data_engineer_skills(self):
        print("\n[V19] 2. Testing Data Engineer Skill Discipline...")
        # Direct check on Role Policy first
        role_skills = data_loader.get_categories_for_role("Data Engineer")
        print(f"   -> Data Engineer Categories: {role_skills}")
        self.assertNotIn("Web Development", role_skills, "Data Engineer policy contaminated with Web Dev!")

    # TEST 3: Arabic Lock
    # Arabic query -> Arabic response narrative
    def test_arabic_lock(self):
        print("\n[V19] 3. Testing Arabic Language Lock...")
        res = self._run_async(self._chat("ازاي ابقى داتا ساينتست؟"))
        
        # Check narrative fields
        print(f"   -> Answer: {res.answer[:50]}...")
        self.assertTrue(any("\u0600" <= c <= "\u06FF" for c in res.answer), "Answer is not Arabic!")
        self.assertTrue(any("\u0600" <= c <= "\u06FF" for c in res.followup_question), "Followup is not Arabic!")

    # TEST 4: Exploration UX
    # "مش عارف اتعلم ايه" -> EXPLORATION intent + Guidelines questions
    def test_exploration_ux(self):
        print("\n[V19] 4. Testing Exploration UX...")
        res = self._run_async(self._chat("مش عارف ابدأ منين"))
        
        print(f"   -> Intent: {res.intent}")
        self.assertEqual(res.intent, IntentType.EXPLORATION, "Failed to classify as EXPLORATION")
        self.assertIn("1️⃣", res.answer, "Did not return guided questions!")

    # TEST 5: No Random Fill for Low Retrieval
    # Rare query -> Don't force fill 3 randoms
    def test_no_random_fill(self):
        print("\n[V19] 5. Testing Anti-Random-Fill (MLOps)...")
        # 'MLOps' might find 0 or 1 course, definitely not 3 specific ones.
        # Should NOT force fill with "Introduction to Programming" just to hit 3.
        res = self._run_async(self._chat("MLOps courses"))
        
        print(f"   -> Returned {len(res.courses)} courses")
        # If it found 0, great. If found 1, great.
        # If found 3, check if they are actually relevant (title check)
        if len(res.courses) == 3:
            titles = [c.title.lower() for c in res.courses]
            print(f"   -> Titles: {titles}")
            # If all are generic, fail.
            is_generic = all("mlops" not in t and "machine learning" not in t and "deployment" not in t for t in titles)
            self.assertFalse(is_generic, "Force-filled irrelevant courses for MLOps!")

if __name__ == '__main__':
    unittest.main()

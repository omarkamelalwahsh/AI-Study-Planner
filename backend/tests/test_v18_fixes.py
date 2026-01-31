"""
V18 Production Fixes Tests
Tests for the UX improvements, Role mapping corrections, and Strict No-Match handling.
Run with: python -m pytest backend/tests/test_v18_fixes.py -v
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
from pipeline.intent_router import IntentRouter
from pipeline.response_builder import ResponseBuilder

class TestV18Fixes(unittest.TestCase):
    """V18 Production Fixes Tests (UX, Mapping, No-Match)"""
    
    @classmethod
    def setUpClass(cls):
        print("\n[V18 TESTS] Loading Data...")
        data_loader.load_all()

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _chat(self, msg: str, sid: str = "v18_test"):
        return await chat(ChatRequest(message=msg, session_id=sid))
    
    # --- FIX 1: Guided Exploration UX ---
    def test_exploration_intent_trigger(self):
        """Test that specific phrases trigger EXPLORATION intent."""
        print("\n[V18] Testing EXPLORATION intent triggers...")
        triggers = [
            "مش عارف أتعلم إيه",
            "I don't know what to learn",
            "عايز حاجة تفتحلي شغل",
            "ابدأ منين"
        ]
        
        for msg in triggers:
            res = self._run_async(self._chat(msg, sid="explore_test"))
            self.assertEqual(res.intent, IntentType.EXPLORATION, f"Failed to detect EXPLORATION for: {msg}")
            self.assertIn("1️⃣", res.answer, "Answer missing guided questions structure")
            print(f"   -> Detected EXPLORATION for: '{msg}'")

    # --- FIX 2: Accurate Role Mapping ---
    def test_data_engineer_mapping(self):
        """Test that Data Engineer role maps to correct skills (SQL, ETL, etc)."""
        print("\n[V18] Testing Data Engineer mapping...")
        role = "Data Engineer"
        policy = data_loader.get_categories_for_role(role)
        priority = data_loader.ROLE_SKILL_PRIORITY.get(role, [])
        
        print(f"   -> Role: {role}")
        print(f"   -> Policy: {policy}")
        print(f"   -> Priority Skills: {priority}")
        
        self.assertIn("Technology Applications", policy)
        self.assertIn("SQL", priority)
        self.assertIn("ETL", priority)
        self.assertIn("Data Warehouse", priority)

    def test_data_analyst_arabic_alias(self):
        """Test Arabic alias mapping for Data Analyst."""
        print("\n[V18] Testing Data Analyst Arabic alias...")
        normalized = data_loader.ROLE_ARABIC_ALIASES.get("محلل بيانات")
        self.assertEqual(normalized, "Data Analyst")
        
        policy = data_loader.get_categories_for_role(normalized)
        self.assertIn("Business Intelligence", policy)
        print(f"   -> 'محلل بيانات' mapped to {normalized} with correct policy.")

    # --- FIX 3: Logical No-Match Handling ---
    def test_blockchain_fallback(self):
        """Test strict fallback for 'Blockchain' query."""
        from llm.groq_client import GroqClient
        print("\n[V18] Testing Blockchain fallback...")
        
        rb = ResponseBuilder(GroqClient())
        answer, _, _, _, _, _, _, _, _, _, _ = self._run_async(rb.build_fallback("Blockchain courses", "Blockchain"))
        
        print(f"   -> Answer: {answer}")
        self.assertIn("Data Security", answer)
        self.assertIn("Programming", answer)
        self.assertNotIn("Supply Chain", answer) # Should NOT suggest random stuff
        self.assertNotIn("Hacking", answer)

    def test_ai_fallback(self):
        """Test strict fallback for 'Artificial Intelligence' query."""
        from llm.groq_client import GroqClient
        print("\n[V18] Testing AI fallback...")
        
        rb = ResponseBuilder(GroqClient())
        answer, _, _, _, _, _, _, _, _, _, _ = self._run_async(rb.build_fallback("AI courses", "Artificial Intelligence"))
        
        print(f"   -> Answer: {answer}")
        self.assertIn("Technology Applications", answer)
        self.assertIn("Programming", answer)


if __name__ == '__main__':
    unittest.main()

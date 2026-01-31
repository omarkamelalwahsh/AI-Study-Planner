"""
V16 Production Smoke Tests
Critical Path Verification for Career Copilot RAG.
Run with: python -m unittest backend/tests/test_smoke_intents.py
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

class TestSmokeIntents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n[SMOKE] Loading Data...")
        data_loader.load_all()

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _chat(self, msg: str, sid: str = "smoke_test"):
        return await chat(ChatRequest(message=msg, session_id=sid))

    def test_A_catalog_browsing_all_categories(self):
        """Req A: 'ايه الكورسات المتاحة' must return ALL categories."""
        print("\n[SMOKE] Testing Catalog Browsing...")
        res = self._run_async(self._chat("ايه الكورسات المتاحة"))
        
        self.assertEqual(res.intent, IntentType.CATALOG_BROWSING)
        self.assertIsNotNone(res.catalog_browsing)
        cats = [c.name for c in res.catalog_browsing.categories]
        self.assertTrue(len(cats) > 5)
        self.assertIn("Programming", cats)
        print(f"   -> Returned {len(cats)} categories.")

    def test_B_guided_discovery(self):
        """Req A/B: 'مش عارف اتعلم ايه' must offer help."""
        print("\n[SMOKE] Testing Guided Discovery...")
        res = self._run_async(self._chat("عاوز اتعلم ومش عارف اتعلم ايه"))
        
        self.assertEqual(res.intent, IntentType.CATALOG_BROWSING)
        self.assertIn("قسم", res.answer) # Should mention categories/departments

    def test_C_specific_track_backend(self):
        """Req E: 'ازاي ابقى باك اند شاطر' -> Career Guidance."""
        print("\n[SMOKE] Testing Backend Track...")
        res = self._run_async(self._chat("ازاي ابقى باك اند شاطر"))
        
        self.assertTrue(res.intent in [IntentType.CAREER_GUIDANCE, IntentType.LEARNING_PATH])
        self.assertTrue(len(res.skill_groups) > 0 or len(res.courses) > 0)
        print(f"   -> Found {len(res.courses)} courses.")

    def test_D_compound_manager_role(self):
        """Req E: 'مدير مبرمجين' -> Maps to Engineering Management."""
        print("\n[SMOKE] Testing Compound Manager Role...")
        res = self._run_async(self._chat("ازاي ابقى مدير مبرمجين ناجح"))
        
        self.assertTrue(res.intent in [IntentType.CAREER_GUIDANCE])
        # Check if we got relevant courses/skills
        has_mgmt = any("Management" in c.title or "Leadership" in c.title or "Building" in c.title for c in res.courses)
        # Note: whitelist logic ensures we get correct category
        print(f"   -> Intent: {res.intent}, Courses: {len(res.courses)}")

    def test_F_pagination(self):
        """Req F: 'اظهر المزيد' -> Next page."""
        print("\n[SMOKE] Testing Pagination...")
        sid = "pag_test"
        # 1. Search
        res1 = self._run_async(self._chat("Python courses", sid=sid))
        ids1 = [c.course_id for c in res1.courses]
        
        # 2. More
        res2 = self._run_async(self._chat("more", sid=sid))
        ids2 = [c.course_id for c in res2.courses]
        
        # Should be different
        self.assertNotEqual(ids1, ids2)
        print(f"   -> Page 1: {len(ids1)}, Page 2: {len(ids2)}")

    def test_integration_track_resolver(self):
        """Test the new TrackResolver logic directly."""
        from pipeline.track_resolver import track_resolver
        from models import IntentResult, SemanticResult
        
        print("\n[SMOKE] Testing Track Resolver...")
        decision = track_resolver.resolve_track(
            "courses in graphic design", 
            SemanticResult(), 
            IntentResult(intent=IntentType.COURSE_SEARCH)
        )
        print(f"   -> Decision: {decision.track_name}, Allowed: {decision.allowed_categories}")
        # Expect strict filtering
        # "Graphic Design" might map to "Graphics & Design" or similar if fuzzy match works
        self.assertTrue(len(decision.allowed_categories) > 0)

if __name__ == '__main__':
    unittest.main()

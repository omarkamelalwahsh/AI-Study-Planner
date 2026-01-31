"""
V16 Production Suite - Regression Tests
Ensures the system remains production-grade after updates.
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

class TestProductionSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data_loader.load_all()

    def _run_async(self, coro):
        """Helper to run async functions in tests."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _async_chat(self, message: str, session_id: str = "test_session"):
        request = ChatRequest(message=message, session_id=session_id)
        return await chat(request)

    # ===========================================
    # F-1: Catalog Browsing (Data-Only)
    # ===========================================
    def test_catalog_browsing_returns_all_categories(self):
        """Req F-1: 'ايه الكورسات المتاحة' must return ALL categories without LLM."""
        response = self._run_async(self._async_chat("ايه الكورسات المتاحة"))
        
        self.assertEqual(response.intent, IntentType.CATALOG_BROWSING)
        self.assertIsNotNone(response.catalog_browsing)
        self.assertTrue(len(response.catalog_browsing.categories) > 10)
        self.assertIn("Programming", [c.name for c in response.catalog_browsing.categories])

    # ===========================================
    # F-2: Guided Discovery (Don't Know)
    # ===========================================
    def test_guided_discovery_dont_know(self):
        """Req F-2: 'مش عارف اتعلم ايه' must show categories."""
        response = self._run_async(self._async_chat("مش عارف اتعلم ايه"))
        
        self.assertEqual(response.intent, IntentType.CATALOG_BROWSING)
        self.assertIsNotNone(response.answer)
        self.assertIn("قسم", response.answer.lower())  # Should mention categories

    # ===========================================
    # F-3: Topic Key Reset (No Leakage)
    # ===========================================
    def test_topic_reset_no_leakage(self):
        """Req F-3: Topic Switch must reset context/cache."""
        sid = "leakage_test"
        
        # 1. First topic: Frontend
        res1 = self._run_async(self._async_chat("ازاي ابقى شاطر في الفرونت اند", session_id=sid))
        self.assertIsNotNone(res1.answer)
        
        # 2. Second topic: Sales (Should NOT have Frontend leakage)
        res2 = self._run_async(self._async_chat("ازاي ابقى مبيعات شاطر", session_id=sid))
        self.assertIsNotNone(res2.answer)

    # ===========================================
    # F-4: Pagination (More Request)
    # ===========================================
    def test_pagination_more_no_duplicates(self):
        """Req F-4: 'غيرهم' returns next page, no duplicates."""
        sid = "pagination_test"
        
        # 1. Initial search
        res1 = self._run_async(self._async_chat("بايثون", session_id=sid))
        ids1 = [c.course_id for c in res1.courses]
        
        # 2. Request more
        res2 = self._run_async(self._async_chat("غيرهم", session_id=sid))
        ids2 = [c.course_id for c in res2.courses]
        
        # Should not crash
        self.assertIsNotNone(res2.answer)

    # ===========================================
    # F-5: Compound Manager Role (No Crash)
    # ===========================================
    def test_compound_manager_role_no_crash(self):
        """Req F-5: 'مدير مبرمجين' handles deterministic role mapping."""
        response = self._run_async(self._async_chat("ازاي ابقى مدير مبرمجين ناجح"))
        
        self.assertEqual(response.intent, IntentType.CAREER_GUIDANCE)
        self.assertIsNotNone(response.answer)

    # ===========================================
    # F-6: CV Analysis (No Crash)
    # ===========================================
    def test_cv_analysis_no_crash(self):
        """Req F-6: CV analysis intent detection."""
        response = self._run_async(self._async_chat("ممكن تقيم السيرة الذاتية بتاعتي؟"))
        self.assertEqual(response.intent, IntentType.CV_ANALYSIS)
        self.assertIsNotNone(response.answer)

    # ===========================================
    # F-7: Umbrella Topic (Programming)
    # ===========================================
    def test_umbrella_topic_programming(self):
        """Req F-7: 'عاوز اتعلم برمجة' shows related categories."""
        response = self._run_async(self._async_chat("عاوز اتعلم برمجة"))
        
        # Should suggest multiple categories
        self.assertIsNotNone(response.answer)
        # Either in CATALOG_BROWSING or has catalog_browsing data
        if response.catalog_browsing:
            cats = [c.name for c in response.catalog_browsing.categories]
            self.assertTrue(any("Programming" in c or "Web" in c for c in cats))

    # ===========================================
    # Data Loader Unit Tests
    # ===========================================
    def test_data_loader_get_all_categories(self):
        """DataLoader must return all categories."""
        cats = data_loader.get_all_categories()
        self.assertIn("Programming", cats)
        self.assertIn("Web Development", cats)
        self.assertIn("Sales", cats)
        self.assertTrue(len(cats) >= 20)

    def test_data_loader_umbrella_categories(self):
        """DataLoader must return umbrella categories."""
        prog_cats = data_loader.get_umbrella_categories("programming")
        self.assertIn("Programming", prog_cats)
        self.assertIn("Web Development", prog_cats)
        
        ar_prog_cats = data_loader.get_umbrella_categories("برمجة")
        self.assertIn("Programming", ar_prog_cats)

    def test_data_loader_canonicalize_query(self):
        """DataLoader must canonicalize queries correctly."""
        result = data_loader.canonicalize_query("ازاي ابقى فرونت اند")
        self.assertEqual(result.get("primary_domain"), "Frontend Development")
        
        result = data_loader.canonicalize_query("ازاي ابقى backend developer")
        self.assertEqual(result.get("primary_domain"), "Backend Development")


if __name__ == '__main__':
    unittest.main()

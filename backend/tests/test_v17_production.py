"""
V17 Production Tests
Tests for the production hardening rules: no crashes, no zero results, category honesty, disambiguation resolution.
Run with: python -m pytest backend/tests/test_v17_production.py -v
"""
import unittest
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import chat
from models import ChatRequest, IntentType, IntentResult
from data_loader import data_loader


class TestV17ProductionRules(unittest.TestCase):
    """V17 Production Hardening Tests"""
    
    @classmethod
    def setUpClass(cls):
        print("\n[V17 TESTS] Loading Data...")
        data_loader.load_all()

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _chat(self, msg: str, sid: str = "v17_test"):
        return await chat(ChatRequest(message=msg, session_id=sid))

    # --- RULE 1: Crash-Proof Guards ---
    def test_no_crash_potential_domain(self):
        """RULE 1: No NameError for potential_domain or other undefined variables."""
        print("\n[V17] Testing crash-proof guards...")
        # This query previously caused NameError in relevance_guard
        res = self._run_async(self._chat("show me backend development courses"))
        # Should return 200 with valid schema, not crash
        self.assertIsNotNone(res)
        self.assertIsNotNone(res.intent)
        print(f"   -> Intent: {res.intent}, Courses: {len(res.courses)}")

    # --- RULE 2: Category Normalization ---
    def test_normalize_category_function(self):
        """RULE 2: normalize_category produces correct output."""
        print("\n[V17] Testing normalize_category function...")
        self.assertEqual(data_loader.normalize_category("Leadership & Management"), "leadership and management")
        self.assertEqual(data_loader.normalize_category("  Web Development  "), "web development")
        self.assertEqual(data_loader.normalize_category("Graphics & Design"), "graphics and design")
        print("   -> normalize_category works correctly.")

    def test_catalog_category_honesty(self):
        """RULE 2/4: 'Technology Applications' must be recognized as in catalog."""
        print("\n[V17] Testing category honesty check...")
        # "Technology Applications" is a real category
        res = self._run_async(self._chat("courses in Technology Applications", sid="honesty_test"))
        # Should NOT claim "not in catalog"
        self.assertNotIn("not in catalog", res.answer.lower())
        self.assertNotIn("غير متوفر", res.answer)
        print(f"   -> Answer does not falsely claim 'not in catalog'.")

    # --- RULE 3: No-Zero-Results ---
    def test_no_zero_results_hr_guidance(self):
        """RULE 3: 'ازاي ابقى HR ماهر' should return >= 1 course OR fallback."""
        print("\n[V17] Testing no-zero-results for HR...")
        res = self._run_async(self._chat("ازاي ابقى HR ماهر", sid="hr_test"))
        total_courses = len(res.courses) + len(res.all_relevant_courses)
        self.assertGreater(total_courses, 0, "HR query returned zero courses!")
        print(f"   -> HR query returned {total_courses} total courses.")

    def test_no_zero_results_sales_manager(self):
        """RULE 3: 'ازاي ابقى مدير مبيعات ناجح' should return >= 1 course."""
        print("\n[V17] Testing no-zero-results for Sales Manager...")
        res = self._run_async(self._chat("ازاي ابقى مدير مبيعات ناجح", sid="sales_mgr_test"))
        total_courses = len(res.courses) + len(res.all_relevant_courses)
        self.assertGreater(total_courses, 0, "Sales Manager query returned zero courses!")
        print(f"   -> Sales Manager query returned {total_courses} total courses.")

    # --- RULE 4: Disambiguation Resolution ---
    def test_disambiguation_no_loop(self):
        """RULE 4: After selecting a category, courses are shown, not the same prompt again."""
        print("\n[V17] Testing disambiguation resolution...")
        sid = "disamb_test"
        
        # Step 1: Send broad query that triggers disambiguation
        res1 = self._run_async(self._chat("وريني كورسات برمجة", sid=sid))
        # Should offer category choices
        self.assertIn("category_choice", res1.mode or "")
        print(f"   -> Step 1: Got category choice mode.")
        
        # Step 2: User selects a category (e.g., "Web Development")
        res2 = self._run_async(self._chat("Web Development", sid=sid))
        # Should NOT offer the same category choice again
        # Should return courses OR at least not be "category_choice" mode again
        if res2.mode == "category_choice":
            # If still category_choice, it should be offering DIFFERENT categories
            self.assertNotEqual(res1.answer, res2.answer, "Disambiguation is looping!")
        print(f"   -> Step 2: Mode is '{res2.mode}', Courses: {len(res2.courses)}")

    # --- RULE 5: Grounded Responses ---
    def test_courses_grounded_in_catalog(self):
        """RULE 5: Returned courses must have valid categories from catalog."""
        print("\n[V17] Testing course grounding...")
        res = self._run_async(self._chat("Python programming courses", sid="grounded_test"))
        all_cats = set(data_loader.get_all_categories())
        for c in res.courses:
            if c.category:
                self.assertIn(c.category, all_cats, f"Course category '{c.category}' not in catalog!")
        print(f"   -> All {len(res.courses)} courses have valid categories.")


class TestTrackResolver(unittest.TestCase):
    """Unit tests for TrackResolver."""
    
    @classmethod
    def setUpClass(cls):
        data_loader.load_all()

    def test_track_resolver_uses_normalized_categories(self):
        """TrackResolver should use normalize_category for comparison."""
        from pipeline.track_resolver import track_resolver
        from models import SemanticResult
        
        print("\n[V17] Testing TrackResolver normalization...")
        decision = track_resolver.resolve_track(
            "Graphics & Design courses",
            SemanticResult(),
            IntentResult(intent=IntentType.COURSE_SEARCH)
        )
        # Should find "Graphics & Design" even if whitelist has slight variation
        print(f"   -> Track: {decision.track_name}, Categories: {decision.allowed_categories}")
        # At minimum, should not be empty if user mentioned a real category
        self.assertTrue(len(decision.allowed_categories) > 0 or decision.track_name != "General")


if __name__ == '__main__':
    unittest.main()

import unittest
import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from main import chat
from models import ChatRequest, IntentType
from data_loader import data_loader

class TestProductionRAG(unittest.TestCase):
    def setUp(self):
        data_loader.load_all()

    async def _async_chat(self, message: str):
        request = ChatRequest(message=message)
        return await chat(request)

    def test_1_sales_manager_guidance(self):
        """TEST 1: 'ازاي ابقى مدير مبيعات ناجح' -> Arabic explanation + Sales courses only"""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("ازاي ابقى مدير مبيعات ناجح"))
        
        # 1. Narrative check
        self.assertTrue(len(re.findall(r'[\u0600-\u06FF]', response.answer)) > 20, "Answer must be Arabic")
        
        # 2. Category check
        allowed = data_loader.ROLE_POLICY["مدير مبيعات"]
        for c in response.courses[:3]:
            cat = c.category or ""
            self.assertIn(cat, allowed, f"Dangerous drift! Category {cat} found for Sales role.")

    def test_2_engineering_manager_axes(self):
        """TEST 2: 'ازاي ابقى مدير مبرمجين ناجح' -> Leadership + Programming only"""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("ازاي ابقى مدير مبرمجين ناجح"))
        
        cats = [c.category for c in response.courses]
        # Should have both Leadership and Programming
        has_mgmt = any("Leadership" in c or "Management" in c for c in cats)
        has_tech = any("Programming" in c or "Web Development" in c for c in cats)
        self.assertTrue(has_mgmt, "Engineering Manager must have Leadership/Management courses")
        self.assertTrue(has_tech, "Engineering Manager must have technical Programming courses")

    def test_3_catalog_browsing_fast(self):
        """TEST 3: 'ايه الكورسات المتاحة' -> Show all categories grouped cleanly"""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("ايه الكورسات المتاحة"))
        
        self.assertEqual(response.intent, IntentType.CATALOG_BROWSING)
        self.assertIsNotNone(response.catalog_browsing)
        self.assertTrue(len(response.catalog_browsing.categories) >= 26)

    def test_4_arabic_consistency(self):
        """TEST 4: Arabic input never outputs long English text."""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("اشرحلي مهارات التواصل"))
        
        # Check that answer is predominantly Arabic
        self.assertTrue(data_loader.is_arabic(response.answer))
        # Check skill reasons are Arabic
        for group in response.skill_groups:
             for skill in group.skills:
                  if skill.why:
                       self.assertTrue(len(re.findall(r'[\u0600-\u06FF]', skill.why)) > 0, f"Skill reason '{skill.why}' should be Arabic")

    def test_sales_manager_whitelist(self):
        """Test 'مدير مبيعات' uses Sales + Management whitelist and is Arabic."""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("ازاي ابقى مدير مبيعات شاطر؟"))
        
        # 1. Check Arabic
        self.assertTrue(len(re.findall(r'[\u0600-\u06FF]', response.answer)) > 20, "Answer should be Arabic")
        
        # 2. Check Whitelist in logs/behavior
        # Negotiation or Sales should be present if catalog has them
        cat_names = [c.category for c in response.courses]
        allowed = data_loader.ROLE_POLICY["مدير مبيعات"]
        for cat in cat_names:
            self.assertIn(cat, allowed, f"Category {cat} not in whitelist {allowed}")

    def test_missing_ai_honesty(self):
        """Test 'مدير AI' honesty message."""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("عايز ابقى مدير AI"))
        
        # Should mention catalog doesn't have direct AI track
        self.assertTrue("مفيش مسار AI مباشر" in response.answer or "AI track" in response.answer.lower())

    def test_ambiguous_browsing(self):
        """Test 'مش عارف ابدا بايه' returns catalog browsing."""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("مش عارف ابدا بايه"))
        
        self.assertEqual(response.intent, IntentType.CATALOG_BROWSING)
        self.assertIsNotNone(response.catalog_browsing)
        self.assertTrue(len(response.catalog_browsing.categories) > 10)

if __name__ == '__main__':
    unittest.main()

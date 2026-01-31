import unittest
import asyncio
import sys
import os
import re

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from main import chat
from models import ChatRequest, IntentType
from data_loader import data_loader

class TestExpertAudit(unittest.TestCase):
    def setUp(self):
        data_loader.load_all()

    async def _async_chat(self, message: str):
        request = ChatRequest(message=message)
        return await chat(request)

    def test_frontend_relevance_strict(self):
        """Audit: Frontend query must NOT contain Backend/Database courses."""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("عايز اتعلم فرونت اند"))
        
        # Blacklist for Frontend
        forbidden = ["sql", "mysql", "postgres", "php", "laravel", "django", "flask", "backend", "سيرفر", "داتابيز", "باك"]
        
        for c in response.courses:
            text = (str(c.title).lower() + " " + (str(c.short_desc) if hasattr(c, 'short_desc') else "")).lower()
            for f in forbidden:
                # If it's strictly a backend title, it should fail
                if f in text and not any(k in text for k in ["frontend", "فرونت", "web", "javascript"]):
                     self.fail(f"Expert Audit Failed: Frontend result '{c.title}' contains backend term '{f}'")

    def test_backend_relevance_strict(self):
        """Audit: Backend query must NOT contain UI/Graphics/Design courses."""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("عايز اتعلم باك اند"))
        
        # Blacklist for Backend
        forbidden = ["photoshop", "illustrator", "ui design", "uidesign", "ux", "graphics", "تصميم واجهات", "فوتوشوب"]
        
        for c in response.courses:
            text = (str(c.title).lower() + " " + (str(c.short_desc) if hasattr(c, 'short_desc') else "")).lower()
            for f in forbidden:
                self.assertNotIn(f, text, f"Expert Audit Failed: Backend result '{c.title}' contains UI term '{f}'")

    def test_arabic_coaching_narrative(self):
        """Audit: Narrative fields must be 100% Arabic for Arabic input."""
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(self._async_chat("ازاي ابقى مدير مبيعات"))
        
        # The 'answer' should be Arabic
        self.assertTrue(len(re.findall(r'[\u0600-\u06FF]', response.answer)) > 20)
        
        # The 'why_recommended' in courses should be Arabic
        for c in response.courses[:3]:
            if c.why_recommended:
                 self.assertTrue(len(re.findall(r'[\u0600-\u06FF]', c.why_recommended)) > 0)

if __name__ == '__main__':
    unittest.main()

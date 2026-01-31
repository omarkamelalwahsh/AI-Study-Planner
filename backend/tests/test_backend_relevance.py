import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

import unittest
import asyncio
from main import app
from fastapi.testclient import TestClient
from models import IntentType

client = TestClient(app)

class TestBackendRelevance(unittest.TestCase):
    def test_backend_query_no_wordpress(self):
        """Query: 'ازاي ابقى باك اند شاطر' -> NO WordPress in results."""
        response = client.post("/chat", json={
            "message": "ازاي ابقى باك اند شاطر",
            "session_id": "test_session_backend"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check Top Picks
        courses = data.get("courses", [])
        for c in courses:
            title = c.get("title", "").lower()
            self.assertNotIn("wordpress", title, f"WordPress course found in backend results: {title}")
            self.assertNotIn("ووردبريس", title, f"WordPress course found in backend results: {title}")

    def test_wordpress_explicit(self):
        """Query: 'عايز اتعلم WordPress Plugins' -> WordPress allowed."""
        response = client.post("/chat", json={
            "message": "عايز اتعلم WordPress Plugins",
            "session_id": "test_session_wp"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        courses = data.get("courses", [])
        wp_found = any("wordpress" in c.get("title", "").lower() or "ووردبريس" in c.get("title", "").lower() for c in courses)
        self.assertTrue(wp_found, "WordPress course NOT found when explicitly requested.")

if __name__ == "__main__":
    unittest.main()

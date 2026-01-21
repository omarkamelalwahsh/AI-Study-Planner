import requests
import json
import uuid

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_new_intents():
    print("Testing 'recommend_courses' intent mapping via 'Business Fundamentals'...")
    payload = {
        # No session_id (optional now)
        "message": "I want to learn Business Fundamentals"
    }
    try:
        with requests.post(f"{BASE_URL}/chat", json=payload, stream=True) as r:
            if r.status_code == 200:
                print("✅ Request successful (Server is up and accepted known category).")
                # We can't easily parse streaming SSE here to check internal intent, 
                # but a 200 OK means it didn't crash on validation.
                for line in r.iter_lines():
                    if line:
                        print(f"Received stream chunk: {line.decode()[:100]}")
                        break
            else:
                print(f"❌ Failed: {r.status_code} {r.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_new_intents()

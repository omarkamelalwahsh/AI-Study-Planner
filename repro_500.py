import requests
import json
import uuid

url = "http://localhost:8001/chat"

def test_query():
    print(f"\n--- Testing Query ---")
    payload = {
        "session_id": str(uuid.uuid4()),
        "message": "عايز أبقى Data Scientist"
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error Detail: {response.text}")
        else:
            print("Success")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_query()

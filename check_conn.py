import requests

BASE_URL = "http://localhost:8001"

def test_conn():
    print("Testing /docs...")
    try:
        r = requests.get(f"{BASE_URL}/docs", timeout=5)
        print(f"Status: {r.status_code}")
    except Exception as e:
        print(f"Failed: {e}")

    print("Testing /chat...")
    try:
        payload = {"message": "ping"}
        r = requests.post(f"{BASE_URL}/chat", json=payload, timeout=5)
        print(f"Chat Status: {r.status_code}")
    except Exception as e:
        print(f"Chat Failed: {e}")

if __name__ == "__main__":
    test_conn()

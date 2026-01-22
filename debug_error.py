import requests
import json

BASE_URL = "http://localhost:8001"

def debug_chat():
    print("Debug Chat...")
    payload1 = {"message": "Hello, debug me."}
    try:
        r1 = requests.post(f"{BASE_URL}/chat", json=payload1)
        r1.raise_for_status()
        print("Success")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        try:
            detail = r1.json().get('detail')
            print(f"Error Detail: {detail}")
        except:
            print(f"Raw Response: {r1.text}")
    except Exception as e:
        print(f"Other Error: {e}")

if __name__ == "__main__":
    debug_chat()

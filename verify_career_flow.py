import requests
import json
import time
import sys

# Ensure UTF-8 output even on Windows
if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

BASE_URL = "http://localhost:8001"

def test_chat(message, session_id=None):
    url = f"{BASE_URL}/chat"
    payload = {
        "message": message,
        "session_id": session_id if session_id else ""
    }
    headers = {"Content-Type": "application/json"}
    
    print(u"--- Sending: '{}' (Session: {}) ---".format(message, session_id))
    try:
        start = time.time()
        # High timeout for multiflow
        response = requests.post(url, json=payload, headers=headers, timeout=120) 
        dur = time.time() - start
        print(f"Status: {response.status_code} (took {dur:.2f}s)")
        
        if response.status_code == 200:
            data = response.json()
            intent = data.get("intent")
            answer = data.get("answer", "")
            courses = data.get("courses", [])
            new_sid = data.get("session_id")
            
            print(f"Response Intent: {intent}")
            print(f"Answer Preview: {answer[:300].replace(chr(10), ' ')}...")
            print(f"Courses Found: {len(courses)}")
            
            if courses:
                print(f"First Course: {courses[0].get('title')}")
                
            return new_sid
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

if __name__ == "__main__":
    print(f"Testing against {BASE_URL}")
    
    # 1. English Career Guidance
    sid = test_chat("How to become a Data Scientist?")
    
    time.sleep(2)
    
    # 2. Arabic Career Guidance
    print("\n--- Arabic Test ---")
    test_chat(u"عايز اتعلم تسويق رقمي")

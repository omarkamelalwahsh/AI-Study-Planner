import requests
import json
import uuid

BASE_URL = "http://localhost:8001"

def test_chat():
    print("Starting Chat Verification...")
    
    # Turn 1: Greeting
    payload1 = {"message": "Hello, I want to learn."}
    try:
        r1 = requests.post(f"{BASE_URL}/chat", json=payload1)
        r1.raise_for_status()
        data1 = r1.json()
        session_id = data1.get("session_id")
        print(f"Turn 1 Response: {data1['answer'][:100]}...")
        print(f"Session ID: {session_id}")
    except Exception as e:
        print(f"Turn 1 Failed: {e}")
        return

    if not session_id:
        print("Error: No Session ID returned")
        return

    # Turn 2: Search for Banking Skills
    payload2 = {"message": "I am interested in Banking Skills.", "session_id": session_id}
    try:
        r2 = requests.post(f"{BASE_URL}/chat", json=payload2)
        r2.raise_for_status()
        data2 = r2.json()
        print(f"Turn 2 Response: {data2['answer'][:100]}...")
        courses = data2.get("courses", [])
        print(f"Courses Found: {len(courses)}")
        if courses:
            print(f"First Course: {courses[0]['title']} by {courses[0]['instructor']}")
    except Exception as e:
        print(f"Turn 2 Failed: {e}")
        return

    # Turn 3: Context Question
    payload3 = {"message": "Who is the instructor of that course?", "session_id": session_id}
    try:
        r3 = requests.post(f"{BASE_URL}/chat", json=payload3)
        r3.raise_for_status()
        data3 = r3.json()
        print(f"Turn 3 Response: {data3['answer']}")
        
        # Check if the instructor name from Turn 2 appears in Turn 3
        if courses and courses[0]['instructor'] in data3['answer']:
            print("SUCCESS: Context preserved! Instructor name found in response.")
        elif courses:
            print("WARNING: contextual answer might be vague. Check manually.")
        else:
            print("INFO: No courses found in Turn 2, so Turn 3 context check is limited.")
            
    except Exception as e:
        print(f"Turn 3 Failed: {e}")
        return

if __name__ == "__main__":
    test_chat()

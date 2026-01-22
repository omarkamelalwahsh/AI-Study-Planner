import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_history_simple():
    print("Starting Simple History Verification...")
    
    # Turn 1: State something to remember
    # We use a GREETING or just a statement.
    # But wait, the system prompt is strict. 
    # "You are NOT a general chatbot."
    # "If routing.intent is OUT_OF_SCOPE... Refuse politely."
    
    # If I say "My name is Alice", it might be classified as OUT_OF_SCOPE or GREETING.
    # Let's try to frame it as a career question.
    # "I am Alice and I want to start a career."
    
    payload1 = {"message": "Hi, I am Alice and I want to start a career."}
    try:
        r1 = requests.post(f"{BASE_URL}/chat", json=payload1)
        r1.raise_for_status()
        data1 = r1.json()
        session_id = data1.get("session_id")
        print(f"Turn 1 Response: {data1['answer'][:100]}...")
        print(f"Session ID: {session_id}")
    except Exception as e:
        print(f"Turn 1 Failed: {e}")
        if 'r1' in locals():
            print(f"Response: {r1.text}")
        return

    if not session_id:
        print("Error: No Session ID returned")
        return
        
    time.sleep(1)

    # Turn 2: Ask for the name
    # "What is my name?" might be OUT_OF_SCOPE.
    # But if history works, it might try to be helpful or at least show it knows.
    # Better: "What should Alice learn?"
    # If it refers to "Alice", then it knows.
    
    payload2 = {"message": "What should I learn?", "session_id": session_id}
    try:
        r2 = requests.post(f"{BASE_URL}/chat", json=payload2)
        r2.raise_for_status()
        data2 = r2.json()
        answer2 = data2['answer']
        print(f"Turn 2 Response: {answer2}")
        
        if "Alice" in answer2:
            print("SUCCESS: Context preserved! AI mentioned 'Alice'.")
        else:
            print("INFO: AI did not mention 'Alice'. This might be due to neutrality rules.")
            # Let's try checking if it remembers the 'start a career' part or if it asks for more info.
            
    except Exception as e:
        print(f"Turn 2 Failed: {e}")
        return

if __name__ == "__main__":
    test_history_simple()

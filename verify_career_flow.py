
import requests
import json
import sys

# Force UTF-8 encoding for console output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_URL = "http://localhost:8001"

def test_chat(message):
    print(f"\n\n--- Testing Message: '{message}' ---")
    url = f"{BASE_URL}/chat"
    payload = {
        "message": message,
        "history": [], # Empty history for fresh context
        "intent_override": "CAREER_GUIDANCE" # Force intent if possible, or let classifier handle it
    }
    
    # Note: verify user model doesn't allow intent_override usually, but let's try standard format
    # Checking app/models.py or valid payload might be needed. 
    # Usually it's just {"message": "...", "history": ...}
    
    clean_payload = {
        "message": message,
        "history": []
    }

    try:
        response = requests.post(url, json=clean_payload)
        response.raise_for_status()
        data = response.json()
        
        print("Status Code:", response.status_code)
        
        # Parse the structured response
        content = data.get("message", "")
        print("\nResponse Content:\n")
        print(content)
        
        # Simple validation
        if "Role" in content or "Area" in content or "Relevant course" in content:
            print("\n[PASS] Response seems to follow the structural guidelines.")
        else:
            print("\n[WARNING] Response might not follow specific formatting.")
            
    except Exception as e:
        print(f"[ERROR] Failed to contact server: {e}")
        if 'response' in locals():
            print(response.text)

if __name__ == "__main__":
    print("Verifying Career Guidance Flow...")
    
    # Test 1: Data Scientist (English)
    test_chat("how to become a data scientist")
    
    # Test 2: Sales Manager (Arabic)
    test_chat("كيف اصبح مدير مبيعات ناجح")

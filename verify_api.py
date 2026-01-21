
import http.client
import json
import sys

def verify_chat():
    conn = http.client.HTTPConnection("127.0.0.1", 8000)
    payload = json.dumps({
        "messages": [{"role": "user", "content": "Hello, this is a test check."}]
    })
    headers = {
        'Content-Type': 'application/json'
    }
    
    print("Sending POST /api/v1/chat request...")
    conn.request("POST", "/api/v1/chat", payload, headers)
    
    response = conn.getresponse()
    print(f"Status: {response.status}")
    print(f"Reason: {response.reason}")
    
    data = response.read().decode('utf-8')
    print(f"Response Data: {data}")
    with open("last_error.log", "w", encoding="utf-8") as f:
        f.write(data)
    
    if response.status == 200:
        print("✅ Success: API responded with 200.")
        if "X-Session-Id" in response.headers:
             print(f"✅ X-Session-Id header found: {response.headers['X-Session-Id']}")
        else:
             print("⚠️ X-Session-Id header missing.")
    else:
        print(f"❌ Failed: API returned {response.status}")
        sys.exit(1)
        
    conn.close()

if __name__ == "__main__":
    verify_chat()

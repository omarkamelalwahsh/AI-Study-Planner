
import http.client
import json

def trigger_init():
    conn = http.client.HTTPConnection("127.0.0.1", 8000)
    print("Triggering /api/v1/init_db_secret...")
    conn.request("GET", "/api/v1/init_db_secret")
    response = conn.getresponse()
    data = response.read().decode('utf-8')
    print(f"Status: {response.status}")
    print(f"Data: {data}")
    conn.close()

if __name__ == "__main__":
    trigger_init()

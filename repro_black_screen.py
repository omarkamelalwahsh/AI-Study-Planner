import asyncio
from main import app
from models import ChatRequest
import json

async def test_black_screen():
    # Simulate the query that caused the black screen
    request = ChatRequest(message="عاوز اتعلم فرونت اند", session_id="test_session")
    
    # We call the chat endpoint directly
    from main import chat
    try:
        response = await chat(request)
        print("SUCCESS")
        # print(response.json())
    except Exception as e:
        print(f"FAILED with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_black_screen())

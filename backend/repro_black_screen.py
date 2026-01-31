import asyncio
import sys
import os

# Add current directory to path so it can find local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import chat
from models import ChatRequest
import json
import logging

# Disable logging to keep output clean, or set to INFO to see what's happening
logging.basicConfig(level=logging.INFO)

async def test_black_screen():
    # Simulate the query that caused the black screen
    request = ChatRequest(message="عاوز اتعلم فرونت اند", session_id="test_session")
    
    print(f"Testing query: {request.message}")
    try:
        response = await chat(request)
        print("\n--- RESPONSE SUCCESS ---")
        # print(response.dict())
    except Exception as e:
        print(f"\n--- RESPONSE FAILED ---")
        print(f"Error type: {type(e)}")
        print(f"Error message: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_black_screen())

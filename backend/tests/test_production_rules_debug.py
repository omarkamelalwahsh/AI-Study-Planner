import asyncio
import json
import logging
from main import chat
from models import ChatRequest, IntentType

# Disable detailed logging to keep output clean
logging.getLogger("backend.main").setLevel(logging.ERROR)
logging.getLogger("pipeline.retriever").setLevel(logging.ERROR)

async def test_language_lock():
    print("\n[DEBUG] Testing Language Lock")
    
    # Arabic
    req = ChatRequest(message="أنا عايز أتعلم بايثون")
    resp = await chat(req)
    print(f"  Input: {req.message[:5]}...")
    print(f"  Detected Lang: {resp.language}")
    if resp.language != "ar":
        print(f"  FAILED: Expected 'ar', got '{resp.language}'")
    
    # English
    req_en = ChatRequest(message="I want to learn Java")
    resp_en = await chat(req_en)
    print(f"  Input: {req_en.message}")
    print(f"  Detected Lang: {resp_en.language}")
    if resp_en.language != "en":
        print(f"  FAILED: Expected 'en', got '{resp_en.language}'")

async def test_exploration():
    print("\n[DEBUG] Testing Exploration Flow")
    session_id = "debug_exp_999"
    
    # Q1
    req1 = ChatRequest(message="مش عارف أبدأ منين", session_id=session_id)
    resp1 = await chat(req1)
    print(f"  Q1: Intent={resp1.intent}, HasAsk={resp1.ask is not None}")
    
    # Q2
    req2 = ChatRequest(message="شغل جديد", session_id=session_id)
    resp2 = await chat(req2)
    print(f"  Q2: Intent={resp2.intent}, HasAsk={resp2.ask is not None}")

async def run_debug():
    try:
        await test_language_lock()
        await test_exploration()
    except Exception as e:
        print(f"\n[ERROR] Test crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_debug())

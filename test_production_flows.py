import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from main import chat
from models import ChatRequest, IntentType
import logging

# Disable heavy logging
logging.basicConfig(level=logging.ERROR)

async def test_flows():
    print("🚀 Starting Production Verification Tests...")
    
    # Test 1: Catalog Browsing (Full)
    print("\n[Test 1] Query: 'ايه الكورسات المتاحة'")
    req1 = ChatRequest(message="ايه الكورسات المتاحة", session_id="test1")
    res1 = await chat(req1)
    if res1.intent == IntentType.CATALOG_BROWSING and res1.catalog_browsing:
        print(f"✅ Success: Returned {len(res1.catalog_browsing.categories)} categories")
    else:
        print(f"❌ Failed: Intent={res1.intent}")

    # Test 2: Broad Topic Suggestion
    print("\n[Test 2] Query: 'اتعلم برمجة'")
    req2 = ChatRequest(message="اتعلم برمجة", session_id="test2")
    res2 = await chat(req2)
    # Broad queries <= 4 words hit fast path which is CATALOG_BROWSING or disambiguation
    if res2.catalog_browsing and len(res2.catalog_browsing.categories) > 0:
        print(f"✅ Success: Suggested {len(res2.catalog_browsing.categories)} tracks")
        print(f"   Tracks: {[c.name for c in res2.catalog_browsing.categories]}")
    else:
        print(f"❌ Failed: No suggestions. Intent={res2.intent}")

    # Test 3: Specific Search (Top Picks vs Relevant)
    print("\n[Test 3] Query: 'python advanced courses'")
    req3 = ChatRequest(message="python advanced courses", session_id="test3")
    res3 = await chat(req3)
    if res3.courses and res3.all_relevant_courses:
        print(f"✅ Success: Top Picks={len(res3.courses)}, All Relevant={len(res3.all_relevant_courses)}")
    elif res3.courses:
         print(f"✅ Success: Only Top Picks={len(res3.courses)}")
    else:
        print(f"❌ Failed: No courses found")

    # Test 4: CV Analysis Schema Safety
    print("\n[Test 4] Query: 'قيم المشروع لبرمجة الموقع'")
    req4 = ChatRequest(message="قيم المشروع لبرمجة الموقع", session_id="test4")
    res4 = await chat(req4)
    if res4.intent in [IntentType.CV_ANALYSIS, IntentType.PROJECT_IDEAS, IntentType.CAREER_GUIDANCE]:
        print(f"✅ Success: Intent={res4.intent}")
    else:
        print(f"❌ Failed: Intent={res4.intent}")

    print("\n🏆 Verification Complete!")

if __name__ == "__main__":
    asyncio.run(test_flows())

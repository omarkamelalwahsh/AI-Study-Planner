"""
Verification script to test the search pipeline restructuring.
This script tests various query types to ensure 0% recall issue is fixed.
"""
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.search.router import SearchRouter
from app.db import SessionLocal
from app.models import Course

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_query(query, expected_min_results=1):
    """Test a single query and print results"""
    print(f"\n🔍 Query: '{query}'")
    
    try:
        result = SearchRouter.route_query(query)
        
        route = result.get("route", "unknown")
        status = result.get("status", "unknown")
        reasoning = result.get("reasoning", "")
        
        # Count total results
        results_by_level = result.get("results_by_level", {})
        total_results = sum(len(v) for v in results_by_level.values())
        
        print(f"   Route: {route}")
        print(f"   Status: {status}")
        print(f"   Total Results: {total_results}")
        print(f"   Reasoning: {reasoning}")
        
        if total_results > 0:
            print(f"   ✅ PASS (Expected >= {expected_min_results})")
            # Show first 3 results
            all_results = []
            for level, courses in results_by_level.items():
                all_results.extend(courses)
            
            print(f"   Sample Results:")
            for i, course in enumerate(all_results[:3]):
                print(f"      {i+1}. {course.get('title', 'N/A')} ({course.get('category', 'N/A')})")
        else:
            if expected_min_results > 0:
                print(f"   ❌ FAIL (Expected >= {expected_min_results}, got 0)")
            else:
                print(f"   ✅ PASS (Expected 0)")
        
        return total_results >= expected_min_results
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print_section("Search Pipeline Verification")
    
    # Get database stats
    db = SessionLocal()
    try:
        total_courses = db.query(Course).count()
        categories = db.query(Course.category).distinct().count()
        print(f"\n📊 Database Stats:")
        print(f"   Total Courses: {total_courses}")
        print(f"   Categories: {categories}")
    finally:
        db.close()
    
    # Test Cases
    test_cases = [
        # Strict Keyword Tests
        ("python", 1, "Strict keyword - should find Python courses"),
        ("javascript", 1, "Strict keyword - should find JavaScript courses"),
        ("sql", 1, "Strict keyword - should find SQL courses"),
        ("git", 1, "Strict keyword - should find Git courses"),
        ("react", 1, "Strict keyword - should find React courses"),
        
        # Arabic Tests
        ("بايثون", 1, "Arabic - should map to 'python'"),
        ("جافاسكريبت", 1, "Arabic - should map to 'javascript'"),
        
        # Category Tests
        ("data science", 1, "Category - should return all Data Science courses"),
        ("web development", 1, "Category - should return all Web Development courses"),
        ("machine learning", 1, "Category - should return all ML courses"),
        
        # Mixed Arabic/English
        ("عاوز اتعلم python", 1, "Mixed - Arabic intent + English keyword"),
        ("كورس javascript", 1, "Mixed - Arabic + English"),
        
        # Generic queries (should still work)
        ("learn programming", 1, "Generic learning query"),
        ("data analysis", 1, "Topic search"),
    ]
    
    print_section("Running Test Cases")
    
    passed = 0
    failed = 0
    
    for query, expected_min, description in test_cases:
        print(f"\n📝 Test: {description}")
        if test_query(query, expected_min):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print_section("Summary")
    total = passed + failed
    print(f"\n✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {failed}/{total}")
    print(f"📊 Success Rate: {(passed/total)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! The 0% recall issue is fixed.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Review the output above.")

if __name__ == "__main__":
    main()

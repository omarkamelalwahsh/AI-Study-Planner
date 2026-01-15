"""
Quick diagnostic test for search API endpoint.
Tests actual search results through the router to verify fixes.
"""
import requests
import json
from bs4 import BeautifulSoup
import re

BASE_URL = "http://localhost:8000"

def extract_scores_from_html(html_content):
    """Extract scores from HTML response"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all course cards
    cards = soup.find_all('div', class_='course-card')
    results = []
    
    for card in cards:
        title_elem = card.find('h3')
        title = title_elem.text.strip() if title_elem else 'N/A'
        
        # Look for score in the card (might be in a data attribute or text)
        score_text = card.get('data-score', '')
        if not score_text:
            # Try to find score in text
            text = card.get_text()
            score_match = re.search(r'Score[:\s]+([\d.]+)', text)
            if score_match:
                score_text = score_match.group(1)
        
        results.append({
            'title': title,
            'score': float(score_text) if score_text else None
        })
    
    return results

def test_search(query, description):
    print("=" * 70)
    print(f"TEST: {description}")
    print(f"Query: '{query}'")
    print("=" * 70)
    
    try:
        # Use POST with form data
        response = requests.post(
            f"{BASE_URL}/search",
            data={
                'query_text': query,
                'weeks': 4,
                'hours_per_week': 10
            }
        )
        
        if response.status_code == 200:
            # Parse HTML to extract info
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find search message
            message_elem = soup.find('div', class_='search-message')
            message = message_elem.text.strip() if message_elem else 'N/A'
            
            print(f"Status: Success")
            print(f"Message: {message}")
            
            # Count results by level
            for level in ['Beginner', 'Intermediate', 'Advanced']:
                level_section = soup.find('div', {'data-level': level})
                if level_section:
                    cards = level_section.find_all('div', class_='course-card')
                    if cards:
                        print(f"\n{level} ({len(cards)} results):")
                        for i, card in enumerate(cards[:5], 1):
                            title_elem = card.find('h3') or card.find('div', class_='course-title')
                            title = title_elem.text.strip()[:45] if title_elem else 'N/A'
                            print(f"  {i}. {title}")
            
            print(f"\n✅ Test completed successfully")
        else:
            print(f"ERROR: Status {response.status_code}")
            print(response.text[:200])
    except Exception as e:
        print(f"ERROR: {e}")
    
    print()

# Run tests
print("\n🔍 SEARCH PIPELINE DIAGNOSTIC TESTS\n")

# Test 1: Python (should show varied scores, not all 1.0 or 0.42)
test_search("python", "Python query - check score distribution")

# Test 2: SQL intermediate (should filter to Intermediate only)
test_search("sql متوسط", "SQL Intermediate - check level filtering")

# Test 3: SQL advanced with محترف (should filter to Advanced only)
test_search("sql محترف", "SQL Advanced (محترف) - check level parsing")

# Test 4: SQL expert (English)
test_search("sql expert", "SQL Expert - check Advanced level")

print("\n" + "=" * 70)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 70)
print("\nWhat to check:")
print("1. Scores should be varied (not all 1.0 or 0.42)")
print("2. Level filtering should work correctly")
print("3. 'محترف' should be recognized as Advanced")
print("4. Band filtering should keep only top scores (within 0.04 of top)")


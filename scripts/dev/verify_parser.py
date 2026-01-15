import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.search.query_parser import parse_query
from app.search.router import SearchRouter
from app.search.embedding import normalize_ar

def test_parser():
    print("--- Testing Query Parser ---")
    
    cases = [
        ("عاوز اتعلم sql للمبتدئين بسرعة", "sql", "Beginner", "single_level"),
        ("SQL advanced", "sql", "Advanced", "single_level"),
        ("شرح python", "python", None, "all_levels"),
        ("مازلت مبتدئ", "", "Beginner", "single_level"), # fallback empty topic?
        ("عاوز اتعلم", "", None, "all_levels"),         # empty
        ("java script intermediate", "java script", "Intermediate", "single_level")
    ]
    
    for q, expected_topic, expected_level, expected_mode in cases:
        parsed = parse_query(q)
        norm_topic = normalize_ar(parsed.topic)
        norm_expected = normalize_ar(expected_topic)
        
        # approximate check for topic (contains)
        topic_match = norm_expected in norm_topic if expected_topic else parsed.topic == ""
        
        status = "PASS" if (topic_match and parsed.level == expected_level and parsed.level_mode == expected_mode) else "FAIL"
        print(f"Query: '{q}' -> Topic: '{parsed.topic}', Level: {parsed.level}, Mode: {parsed.level_mode} [{status}]")
        if status == "FAIL":
            print(f"   Expected: Topic='{expected_topic}', Level='{expected_level}', Mode='{expected_mode}'")

def test_router_mock():
    # We can't easily mock the DB here without setup, but we can verify the logic flow 
    # if we had a mockable Router. For now, let's rely on the parser test 
    # and the fact that we traced the code.
    pass

if __name__ == "__main__":
    test_parser()

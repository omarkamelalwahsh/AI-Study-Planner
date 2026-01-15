import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.search.embedding import is_learning_query

def test_queries():
    queries = [
        ("03 D Max Start Creating your Own Project Material", True),
        ("Java Course", True),
        ("Mental Health", True),
        ("Is this a good course?", False), # Generic opinion -> Should Fail
        ("Is this a good SQL course?", True), # Specific opinion -> Should Pass
        ("recommend", False), # Generic -> Pass? No, has_subject fails.
        ("recommend java", True),
        ("01 Introduction", True),
        ("Start building your first app", True),
        ("What is python", True),
    ]

    print(f"{'Query':<50} | {'Expected':<10} | {'Actual':<10} | {'Result'}")
    print("-" * 90)
    
    all_passed = True
    for q, expected in queries:
        actual = is_learning_query(q)
        result = "PASS" if actual == expected else "FAIL"
        if result == "FAIL":
            all_passed = False
        print(f"{q:<50} | {str(expected):<10} | {str(actual):<10} | {result}")

    if all_passed:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    test_queries()

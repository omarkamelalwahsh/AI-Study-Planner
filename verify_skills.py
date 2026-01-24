"""
verify_skills.py
Test script to verify that `extract_skills_for_role` works as expected.
"""
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.skills import extract_skills_for_role

def test_extraction():
    test_cases = [
        "عايز ابقى مدير مبيعات شاطر",
        "I want to be a Data Scientist",
        "محتاج اشتغل في الماركتينج"
    ]
    
    print("--- Starting Skill Extraction Verification ---")
    
    for case in test_cases:
        print(f"\nInput: {case}")
        try:
            result = extract_skills_for_role(case)
            print(f"Output: {result}")
            
            # Basic validation
            if not result:
                print("FAIL: Empty result")
            elif case == result:
                 print("WARN: Result same as input (Fallback used?)")
            else:
                print("SUCCESS: Extraction occurred")
                
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    test_extraction()

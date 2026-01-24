
import sys
import os
sys.path.append(os.getcwd())

from app.generator import DEVELOPER_PROMPT_TEMPLATE

class Course:
    def __init__(self, course_id, title, description, level, instructor):
        self.course_id = course_id
        self.title = title
        self.description = description
        self.level = level
        self.instructor = instructor

def test_render_logic():
    print("--- Testing Render Mode Logic ---")
    
    # 1. Single Course Scenario
    c1 = Course(course_id="111", title="Leadership 101", description="Intro", level="Beginner", instructor="A")
    catalog_results_single = [c1]
    
    unique_count = len({c.course_id for c in catalog_results_single})
    render_mode_single = "single_course_expand" if unique_count == 1 else "multi_course_grouped"
    
    print(f"Scenario 1 (1 Course): Mode = {render_mode_single}")
    if render_mode_single == "single_course_expand":
        print(" [PASS] Correctly identified Single Course Mode")
    else:
        print(" [FAIL] Failed to identify Single Course Mode")

    # 2. Multi Course Scenario
    c2 = Course(course_id="222", title="Leadership 102", description="Advanced", level="Advanced", instructor="B")
    catalog_results_multi = [c1, c2]
    
    unique_count_multi = len({c.course_id for c in catalog_results_multi})
    render_mode_multi = "single_course_expand" if unique_count_multi == 1 else "multi_course_grouped"
    
    print(f"Scenario 2 (2 Courses): Mode = {render_mode_multi}")
    if render_mode_multi == "multi_course_grouped":
        print(" [PASS] Correctly identified Multi Course Mode")
    else:
        print(" [FAIL] Failed to identify Multi Course Mode")

    # 3. Duplicate Logic Check
    catalog_results_dup = [c1, c1] # Same object twice
    unique_count_dup = len({c.course_id for c in catalog_results_dup})
    render_mode_dup = "single_course_expand" if unique_count_dup == 1 else "multi_course_grouped"
    
    print(f"Scenario 3 (Duplicate Course): Mode = {render_mode_dup}")
    if render_mode_dup == "single_course_expand":
        print(" [PASS] Correctly handled duplicates as Single Course")
    else:
        print(" [FAIL] Duplicate handling failed")

if __name__ == "__main__":
    test_render_logic()

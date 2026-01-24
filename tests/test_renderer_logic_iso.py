
# Unit Test for Render Mode Logic
# Duplicate logic from generator.py to verify correctness in isolation
# implementation: render_mode = "single_course_expand" if len(unique) == 1 else "multi_course_grouped"

class MockCourse:
    def __init__(self, cid):
        self.course_id = cid

def get_render_mode(courses):
    unique = {c.course_id for c in courses}
    return "single_course_expand" if len(unique) == 1 else "multi_course_grouped"

def test_logic():
    print("--- Testing Logic Isolation ---")
    
    # Case 1
    courses1 = [MockCourse("A")]
    mode1 = get_render_mode(courses1)
    print(f"Case 1 (1 Course): {mode1}")
    assert mode1 == "single_course_expand"
    
    # Case 2
    courses2 = [MockCourse("A"), MockCourse("B")]
    mode2 = get_render_mode(courses2)
    print(f"Case 2 (2 Courses): {mode2}")
    assert mode2 == "multi_course_grouped"
    
    # Case 3
    courses3 = [MockCourse("A"), MockCourse("A")]
    mode3 = get_render_mode(courses3)
    print(f"Case 3 (Duplicates): {mode3}")
    assert mode3 == "single_course_expand"
    
    print("ALL LOGIC CHECKS PASSED")

if __name__ == "__main__":
    test_logic()

"""
Quick tests for normalize_text integration
"""

from app.utils.normalize import normalize_text
from app.config.learning_mapping import LEARNING_MAPPING


def test_python_path():
    result = normalize_text("بايثون", LEARNING_MAPPING)
    print(f"Test 1 - Arabic 'بايثون': {result}")
    assert result["type"] == "path"
    assert result["value"] == "python"
    print("✅ PASS")


def test_sql_path():
    result = normalize_text("داتا بيز", LEARNING_MAPPING)
    print(f"Test 2 - Arabic 'داتا بيز': {result}")
    assert result["type"] == "path"
    assert result["value"] == "sql"
    print("✅ PASS")


def test_web_path():
    result = normalize_text("ويب", LEARNING_MAPPING)
    print(f"Test 3 - Arabic 'ويب': {result}")
    assert result["type"] == "path"
    assert result["value"] == "web"
    print("✅ PASS")


def test_intermediate_level():
    result = normalize_text("متوسط", LEARNING_MAPPING)
    print(f"Test 4 - Arabic 'متوسط': {result}")
    assert result["type"] == "level"
    assert result["value"] == "Intermediate"
    print("✅ PASS")


def test_beginner_level():
    result = normalize_text("مبتدئ", LEARNING_MAPPING)
    print(f"Test 5 - Arabic 'مبتدئ': {result}")
    assert result["type"] == "level"
    assert result["value"] == "Beginner"
    print("✅ PASS")


def test_programming_category():
    result = normalize_text("برمجة", LEARNING_MAPPING)
    print(f"Test 6 - Arabic 'برمجة': {result}")
    assert result["type"] == "category"
    assert result["value"] == "Programming"
    print("✅ PASS")


def test_priority_path_over_category():
    # Message contains both path and category terms
    result = normalize_text("عاوز أتعلم بايثون برمجة", LEARNING_MAPPING)
    print(f"Test 7 - Path priority: {result}")
    assert result["type"] == "path"  # Path should win
    assert result["value"] == "python"
    print("✅ PASS - Path has priority over category")


def test_english_python():
    result = normalize_text("python", LEARNING_MAPPING)
    print(f"Test 8 - English 'python': {result}")
    assert result["type"] == "path"
    assert result["value"] == "python"
    print("✅ PASS")


if __name__ == "__main__":
    print("=" * 50)
    print("Testing normalize_text integration")
    print("=" * 50)
    
    test_python_path()
    test_sql_path()
    test_web_path()
    test_intermediate_level()
    test_beginner_level()
    test_programming_category()
    test_priority_path_over_category()
    test_english_python()
    
    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED!")
    print("=" * 50)

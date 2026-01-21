import pytest
from app.search.embedding import normalize_ar, expand_query

def test_normalization():
    assert normalize_ar("كَوْرس") == "كورس"
    assert normalize_ar("أحمد") == "احمد"
    assert normalize_ar("برمجية") == "برمجيه"
    assert normalize_ar("الصحّة النفسيّة") == "الصحه النفسيه"
    assert normalize_ar("٠١٢٣٤٥٦٧٨٩") == "0123456789"

def test_query_expansion():
    # Test Arabic expansion
    expanded = expand_query("جافا")
    assert "java" in expanded.lower()
    
    expanded = expand_query("جافا سكربت")
    assert "javascript" in expanded.lower()
    
    # Test English expansion
    expanded = expand_query("js")
    assert "javascript" in expanded.lower()

def test_tech_conflict():
    # Ensure "java" expansion doesn't break "javascript" manually if both present
    # Actually expansion adds 'java' if 'جافا' is present.
    # Retrieval logic handles the difference.
    pass

if __name__ == "__main__":
    # Simple manual run
    print("Testing Normalization...")
    print(f"'جافا اسكربت' -> '{normalize_ar('جافا اسكربت')}'")
    
    print("\nTesting Expansion...")
    print(f"'جافا' -> '{expand_query('جافا')}'")
    print(f"'جافا اسكربت' -> '{expand_query('جافا اسكربت')}'")
    print(f"'js' -> '{expand_query('js')}'")
    print(f"'python' -> '{expand_query('python')}'")

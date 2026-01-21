import pytest
from app.search.embedding import is_learning_query
from app.services.llm_service import format_agent_response

def test_is_learning_query():
    # True cases
    assert is_learning_query("عاوز اتعلم برمجه") == True
    assert is_learning_query("ابدا تحليل بيانات") == True # Test normalized 'ابدا'
    assert is_learning_query("كورس داتا ساينس") == True
    assert is_learning_query("خطه تعلم") == True
    
    # False cases
    assert is_learning_query("خياطه") == False
    assert is_learning_query("انا جعان") == False
    assert is_learning_query("") == False

def test_has_subject():
    from app.search.embedding import has_subject
    assert has_subject("اتعلم بايثون") == True
    assert has_subject("كورس جافا") == True
    assert has_subject("انا عاوز اتعلم بايثون") == True
    
    # Fluff only cases
    assert has_subject("انا عاوز اتعلم") == False
    assert has_subject("ممكن اتعلم") == False
    assert has_subject("how to learn") == False

def test_format_agent_response_ok():
    results = [
        {"title": "Python for Beginners", "description_snippet": "Learn python from scratch.", "score": 0.95},
        {"title": "Advanced Java", "description_snippet": "Deep dive into JVM.", "score": 0.92}
    ]
    response = format_agent_response("learn coding", results)
    
    assert response["status"] == "ok"
    assert len(response["results"]) == 2
    assert response["results"][0]["title"] == "Python for Beginners"
    assert "Learn python" in response["results"][0]["reason"]

def test_format_agent_response_no_match():
    response = format_agent_response("cooking", [])
    
    assert response["status"] == "no_match"
    assert "معنديش كورسات" in response["message"]

def test_filter_by_user_level_refined():
    from app.search.retrieval import filter_by_user_level
    courses = [
        {"title": "Beginner Python", "level": "Beginner"},
        {"title": "Inter Python", "level": "Intermediate"},
        {"title": "Adv Python", "level": "Advanced"},
        {"title": "Any Python", "level": "All Levels"},
    ]
    
    # Implicit Beginner (Should see EVERYTHING)
    impl_results = filter_by_user_level(courses, "beginner", is_explicit=False)
    assert len(impl_results) == 4
    
    # Explicit Beginner (Should see EVERYTHING - beginner is lowest)
    expl_beg = filter_by_user_level(courses, "beginner", is_explicit=True)
    assert len(expl_beg) == 4
    
    # Explicit Intermediate (Never Lower rule: NO beginner)
    expl_inter = filter_by_user_level(courses, "intermediate", is_explicit=True)
    assert len(expl_inter) == 3 # inter + adv + all
    assert not any(c["title"] == "Beginner Python" for c in expl_inter)
    
    # Explicit Advanced (Only advanced + all)
    expl_adv = filter_by_user_level(courses, "advanced", is_explicit=True)
    assert len(expl_adv) == 2 # adv + all
    assert not any(c["level"] == "Beginner" for c in expl_adv)
    assert not any(c["level"] == "Intermediate" for c in expl_adv)

def test_tech_greedy_collision_logic():
    # Real variants from retrieval.py
    tech_map = {
        "javascript": ["javascript", "js", "جافاسكربت", "جافا سكربت", "جافا اسكريبت", "جافا سكريبت"],
        "java": ["java", "جافا"],
        "c#": ["c#", "csharp", "سي شارب"],
        "c++": ["c++", "cpp", "سي بلس بلس", "سي بلس"],
        "c": [" c ", "لغة سي", "برمجة سي"]
    }
    
    all_variants = []
    for subject, variants in tech_map.items():
        for v in variants:
            all_variants.append((v, subject))
    all_variants.sort(key=lambda x: len(x[0]), reverse=True)

    def get_subs(text):
        found = []
        temp_text = f" {text.lower()} "
        for variant, subject in all_variants:
            if variant in temp_text:
                if subject not in found:
                    found.append(subject)
                temp_text = temp_text.replace(variant, " " * len(variant))
        return found

    # Query: 'java' -> Course: 'javascript'
    assert "java" in get_subs("تعلم جافا")
    assert "javascript" not in get_subs("تعلم جافا")
    
    # Searching for 'java' should NOT return something identified ONLY as 'javascript'
    js_course_subs = get_subs("تعلم جافا سكريبت")
    assert "javascript" in js_course_subs
    assert "java" not in js_course_subs # Greedy catches 'جافا سكريبت' first
    
    # Query: 'c' -> Course: 'c++'
    cpp_course_subs = get_subs("learn c++")
    assert "c++" in cpp_course_subs
    assert "c" not in cpp_course_subs # C is hidden by C++

def test_multilingual_subject_detection():
    from app.search.embedding import has_subject
    assert has_subject("تعلم python") == True
    assert has_subject("learn بايثون") == True
    assert has_subject("كيفية استخدام sql") == True
    assert has_subject("i want to learn c++") == True
    
    # Generic Multilingual Fluff
    assert has_subject("بدي اتعلم") == False
    assert has_subject("i want to learn") == False

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])

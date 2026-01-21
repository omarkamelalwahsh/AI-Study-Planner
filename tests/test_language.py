import pytest
from app.services.chat_service import detect_lang

def test_detect_lang_arabic():
    assert detect_lang("عاوز اتعلم برمجة") == "ar"

def test_detect_lang_english():
    assert detect_lang("I want to become a good python dev") == "en"

def test_detect_lang_mixed_prefers_ar_if_ar_chars_exist():
    assert detect_lang("عاوز learn python") == "ar"

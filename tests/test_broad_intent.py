import pytest
from app.services.chat_service import is_broad_intent

def test_broad_intent_en_true():
    assert is_broad_intent("I want to learn programming", "en") is True

def test_broad_intent_ar_true():
    assert is_broad_intent("عاوز اتعلم برمجة", "ar") is True

def test_broad_intent_false_for_specific():
    assert is_broad_intent("Python web development", "en") is False

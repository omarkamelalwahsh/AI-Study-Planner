import pytest
from unittest.mock import patch
from app.services.chat_service import ChatService

@pytest.fixture
def svc():
    with patch("app.services.chat_service.ChatService.__init__", return_value=None):
        return ChatService()

def test_is_empty_context_blank(svc):
    assert svc.is_empty_context("") is True

def test_is_empty_context_none(svc):
    assert svc.is_empty_context(None) is True

def test_is_empty_context_has_courses(svc):
    txt = "1) Python Basics 2020\n- Category: Programming\n"
    assert svc.is_empty_context(txt) is False

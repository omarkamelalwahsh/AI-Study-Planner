import pytest
import uuid
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.chat_service import ChatService, ChatSessionState
from app.models import ChatSession, ChatMessage

# Mock Data
MOCK_SESSION_ID = str(uuid.uuid4())
INITIAL_STATE = ChatSessionState().model_dump()

@pytest.fixture
def mock_llm_stream():
    with patch("app.services.chat_service.get_llm") as mock_get:
        llm = MagicMock()
        # stream is async generator
        async def async_gen(*args, **kwargs):
            yield "Hello"
            yield " World"
        
        llm.stream = MagicMock(side_effect=async_gen)
        mock_get.return_value = llm
        yield llm

@pytest.fixture
def mock_retriever():
    with patch("app.services.chat_service.CourseRetriever") as mock_cls:
        retriever = MagicMock()
        retriever.get_top_categories.return_value = ["Data Science", "Web Dev"]
        retriever.search.return_value = [] # Default no results
        retriever.format_courses_for_prompt.return_value = ""
        mock_cls.return_value = retriever
        yield retriever

@pytest.fixture
def service(mock_llm_stream, mock_retriever):
    return ChatService("dummy_path")

@pytest.fixture
def mock_db():
    session = MagicMock()
    # Setup query return val for "get session"
    # By default returns None (new session)
    session.query.return_value.filter.return_value.first.return_value = None
    return session

@pytest.mark.asyncio
async def test_new_session_creation(service, mock_db):
    # Test handling a message for a new session
    gen = service.handle_message(MOCK_SESSION_ID, "Hello", mock_db)
    async for _ in gen:
        pass
    
    # Verify session creation was attempted
    # Check if DB add was called for session
    # We expect db.add(ChatSession)
    added_objs = [call.args[0] for call in mock_db.add.call_args_list]
    session_obj = next((obj for obj in added_objs if isinstance(obj, ChatSession)), None)
    
    assert session_obj is not None
    assert str(session_obj.id) == MOCK_SESSION_ID
    assert session_obj.state == INITIAL_STATE
    mock_db.commit.assert_called()

@pytest.mark.asyncio
async def test_load_existing_session(service, mock_db):
    # Setup existing session
    existing_state = ChatSessionState(mode="assessment", assessment_step=5).model_dump()
    existing_session = ChatSession(id=MOCK_SESSION_ID, state=existing_state)
    
    mock_db.query.return_value.filter.return_value.first.return_value = existing_session
    
    gen = service.handle_message(MOCK_SESSION_ID, "Continue", mock_db)
    async for _ in gen:
        pass
    
    # Check that we loaded the state correctly (logic depends on it)
    # logic flow: if assessment_step=5 and max=3 -> should trigger Result
    # We can check the DB save state at the end
    
    # Get the LAST add call for session (state update)
    # Note: handle_message calls db.add(session) at the end
    assert mock_db.commit.called
    
    # We assume logic worked and state updated.
    # Since step was 5 (>=3), it should have gone to 'result' then 'normal'
    # Checking final state saved
    # We can't easily check the object passed to add logic directly if it's the SAME object instance modified
    # We check the attributes of existing_session
    # Ideally, logic sets existing_session.state = new_dict
    
    # If step=5, plan_turn returns "result" -> Post Update: step=6, mode="normal"
    final_state_dict = existing_session.state
    assert final_state_dict["mode"] == "normal"
    assert final_state_dict["last_question_type"] == "result"

@pytest.mark.asyncio
async def test_assessment_trigger_flow(service, mock_db):
    # User asks for "assessment"
    # Setup normal session
    existing_session = ChatSession(id=MOCK_SESSION_ID, state=INITIAL_STATE)
    mock_db.query.return_value.filter.return_value.first.return_value = existing_session
    
    gen = service.handle_message(MOCK_SESSION_ID, "I want an assessment", mock_db)
    async for _ in gen:
        pass
    
    # Expect state transition to assessment mode
    state = existing_session.state
    assert state["mode"] == "assessment"
    assert state["last_question_type"] == "topic_selection"
    
    # Also check that Messages were saved
    # We expect 2 adds (User msg, Assistant msg) + Session update
    # In my logic: add(user), add(assistant), add(session)
    assert mock_db.add.call_count >= 3

@pytest.mark.asyncio
async def test_rag_context_gating(service, mock_db, mock_retriever):
    # 1. Normal mode -> RAG used on message
    existing_session = ChatSession(id=MOCK_SESSION_ID, state=INITIAL_STATE)
    mock_db.query.return_value.filter.return_value.first.return_value = existing_session
    
    mock_retriever.search.reset_mock()
    gen = service.handle_message(MOCK_SESSION_ID, "Python courses", mock_db)
    async for _ in gen: pass
    
    mock_retriever.search.assert_called()
    assert "Python courses" in mock_retriever.search.call_args[0][0]

    # 2. Assessment mode (No topic) -> NO RAG
    state_assessment = ChatSessionState(mode="assessment", assessment_topic=None).model_dump()
    existing_session.state = state_assessment
    mock_retriever.search.reset_mock()
    
    gen = service.handle_message(MOCK_SESSION_ID, "Yes", mock_db)
    async for _ in gen: pass
    
    mock_retriever.search.assert_not_called()

    # 3. Assessment mode (Has topic) -> RAG using TOPIC
    state_topic = ChatSessionState(mode="assessment", assessment_topic="Data Science").model_dump()
    existing_session.state = state_topic
    mock_retriever.search.reset_mock()
    
    gen = service.handle_message(MOCK_SESSION_ID, "Next question", mock_db)
    async for _ in gen: pass
    
    mock_retriever.search.assert_called()
    # Should search for "Data Science" not "Next question"
    assert "Data Science" in mock_retriever.search.call_args[0][0]

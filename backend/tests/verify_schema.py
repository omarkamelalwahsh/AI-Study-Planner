from models import ChatResponse, NextAction, IntentType
import json

def test_chat_response_schema():
    # 1. Test with structured next_actions
    data = {
        "intent": "CAREER_GUIDANCE",
        "answer": "Test answer",
        "next_actions": [
            {"text": "Action 1", "type": "follow_up", "payload": {"foo": "bar"}}
        ],
        "session_state": {}
    }
    
    response = ChatResponse(**data)
    assert len(response.next_actions) == 1
    assert isinstance(response.next_actions[0], NextAction)
    assert response.next_actions[0].text == "Action 1"
    assert response.next_actions[0].payload == {"foo": "bar"}
    
    print("✓ Structured next_actions validation passed")

    # 2. Test JSON dumping
    dumped = response.model_dump()
    assert isinstance(dumped["next_actions"][0], dict)
    assert dumped["next_actions"][0]["text"] == "Action 1"
    
    print("✓ JSON dumping validation passed")

if __name__ == "__main__":
    try:
        test_chat_response_schema()
        print("\nAll schema validations passed! ✓")
    except Exception as e:
        print(f"\nValidation failed: {e}")
        exit(1)

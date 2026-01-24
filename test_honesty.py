import asyncio
import sys
from unittest.mock import MagicMock
from app.generator import generate_final_response
import io

# Mock and Setup
mock_db = MagicMock()
sys.modules['app.database'] = mock_db
mock_settings = MagicMock()
mock_settings.groq_api_key = "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"
mock_settings.groq_max_retries = 2
mock_settings.groq_model = "llama-3.1-8b-instant"
mock_settings.groq_timeout_seconds = 20
sys.modules['app.config'] = MagicMock()
sys.modules['app.config'].settings = mock_settings

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def test_honesty():
    print("Testing Honesty Rule (Zero Courses)...")
    plan = {
        "guidance_intro": "Quantum computing is a complex field.",
        "core_areas": [{"area": "Linear Algebra", "why_it_matters": "Basis of qubits", "actions": ["Study matrices"]}]
    }
    response = generate_final_response(
        user_question="I want to learn Quantum Computing",
        guidance_plan=plan,
        grounded_courses=[],
        language="en"
    )
    print(f"RESPONSE:\n{response}")

if __name__ == "__main__":
    asyncio.run(test_honesty())

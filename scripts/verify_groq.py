from groq import Groq
import os
from app.config import settings

try:
    client = Groq(api_key=settings.groq_api_key)
    print("Groq client initialized successfully.")
except Exception as e:
    print(f"Failed to initialize Groq client: {e}")

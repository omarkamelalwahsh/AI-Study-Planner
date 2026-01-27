"""
Career Copilot RAG Backend - Configuration
Loads environment variables and provides settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8001"))

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Data paths
DATA_DIR = PROJECT_ROOT / "data"
COURSES_CSV = DATA_DIR / "courses.csv"
SKILLS_CATALOG_CSV = DATA_DIR / "skills_catalog_enriched_v2.csv"
SKILL_TO_COURSES_INDEX = DATA_DIR / "skill_to_courses_index.json"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

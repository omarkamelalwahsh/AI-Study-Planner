#!/bin/bash

# setup.sh - One-command setup for Career Copilot

echo "🚀 Setting up Career Copilot..."

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required."
    exit 1
fi

# 2. Venv
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate || source .venv/Scripts/activate

# 3. Dependencies
echo "⬇️ Installing dependencies..."
pip install -r requirements.txt

# 4. Env
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️ Please check .env and update DATABASE_URL if needed."
fi

# 5. Database
echo "🗄️ Initializing Database..."
python scripts/init_db.py

# 6. Indexing
echo "🔍 Building Search Index..."
python scripts/indexing/build_index.py

echo "✅ Setup Complete! Run 'uvicorn app.main:app --reload' to start."

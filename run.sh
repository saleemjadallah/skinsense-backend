#!/bin/bash

# SkinSense AI Backend Startup Script

echo "🚀 Starting SkinSense AI Backend..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found! Please create one from .env.example"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Add openai to requirements if not present
if ! grep -q "openai" requirements.txt; then
    echo "➕ Adding openai to requirements..."
    echo "openai==1.3.5" >> requirements.txt
    pip install openai==1.3.5
fi

# Run the application
echo "✨ Starting FastAPI server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
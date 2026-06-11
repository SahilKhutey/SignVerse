#!/bin/bash
set -e

echo "╔════════════════════════════════════════╗"
echo "║   🤖 SignVerse Robotics - Day 3       ║"
echo "║   Final Demo Build                    ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node 18+"
    exit 1
fi

# Create dirs
mkdir -p data/uploads exports datasets

# Backend setup
if [ ! -d "venv" ]; then
    echo "📦 Creating Python venv..."
    python3 -m venv venv
fi

echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Frontend setup
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing Node dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Verify
echo ""
echo "🔍 Running verification..."
python scripts/verify.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting services..."
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:5173"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start backend in background
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend in background
cd frontend && npm run dev &
FRONTEND_PID=$!

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

# Wait
wait

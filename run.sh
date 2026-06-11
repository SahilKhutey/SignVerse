#!/bin/bash
echo "🤖 Starting SignVerse MVP..."

# Backend
echo "📦 Setting up Python env..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create dirs
mkdir -p data/uploads exports datasets

# Start backend
echo "🚀 Starting FastAPI on :8000..."
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Frontend
echo "🎨 Starting React on :5173..."
cd frontend
npm install
npm run dev &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait

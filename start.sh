#!/bin/bash
# CPT Email Agent — Start Script

PROJECT_DIR="/Users/rushilreddy/Documents/cold-email-agent"

echo "🚀 Starting CPT Email Agent..."
echo ""

# Check for venv
if [ ! -d "$PROJECT_DIR/venv" ]; then
  echo "📦 Creating Python virtual environment..."
  python3 -m venv "$PROJECT_DIR/venv"
fi

# Activate and install deps
source "$PROJECT_DIR/venv/bin/activate"
echo "📦 Installing Python dependencies..."
pip install -r "$PROJECT_DIR/requirements.txt" -q

# Start backend in background
echo "⚡ Starting FastAPI backend on :8000..."
cd "$PROJECT_DIR"
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend to be ready
sleep 3

# Install frontend deps if needed
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
  echo "📦 Installing frontend dependencies..."
  cd "$PROJECT_DIR/frontend"
  npm install -q
fi

# Start frontend
echo "🎨 Starting React dashboard on :5173..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Both services running!"
echo "   Dashboard: http://localhost:5173"
echo "   API:       http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; echo '🛑 Stopped.'; exit" INT
wait

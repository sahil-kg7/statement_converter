#!/usr/bin/env bash
set -e

VENV_DIR="backend/.venv"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

activate_venv() {
  if [ -f "$VENV_DIR/bin/activate" ]; then
    . "$VENV_DIR/bin/activate"
  elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    . "$VENV_DIR/Scripts/activate"
  else
    echo "Virtual environment not found at $VENV_DIR"
    exit 1
  fi
}

echo "=== Installing backend dependencies ==="
python3 -m venv "$VENV_DIR"
activate_venv
pip install -e "$ROOT_DIR/backend[dev]"

echo ""
echo "=== Installing frontend dependencies ==="
npm --prefix "$ROOT_DIR/frontend" install

echo ""
echo "=== Starting backend ==="
cd "$ROOT_DIR/backend"
uvicorn app.main:app --reload &
BACKEND_PID=$!
cd "$ROOT_DIR"

echo "=== Starting frontend ==="
npm --prefix "$ROOT_DIR/frontend" run dev &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both."
echo ""

wait

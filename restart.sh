#!/bin/bash
# Kill any process on ports 8888 and 3000
echo "🔴 Stopping existing servers..."
lsof -ti:8888 | xargs kill -9 2>/dev/null && echo "  ✓ Backend (8888) stopped" || echo "  – Backend not running"
lsof -ti:3000 | xargs kill -9 2>/dev/null && echo "  ✓ Frontend (3000) stopped" || echo "  – Frontend not running"

sleep 1

# Open Backend in a new Terminal window
echo "🟢 Starting Backend..."
osascript -e 'tell application "Terminal"
  do script "cd /Users/happypc/PePeApp/backend && source .venv/bin/activate && uvicorn api.app:app --host 0.0.0.0 --port 8888 --reload"
  set custom title of front window to "PePeApp — Backend"
end tell'

sleep 2

# Open Frontend in a new Terminal window
echo "🟢 Starting Frontend..."
osascript -e 'tell application "Terminal"
  do script "cd /Users/happypc/PePeApp/frontend && pnpm dev"
  set custom title of front window to "PePeApp — Frontend"
end tell'

echo ""
echo "✅ Done! Two Terminal windows opened."
echo "   Backend  → http://localhost:8888"
echo "   Frontend → http://localhost:3000"

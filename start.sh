#!/bin/bash

# PaperMap 启动脚本
# 同时启动后端 API 和前端开发服务器

echo "🗺️  Starting PaperMap..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查数据库是否存在，不存在则初始化
if [ ! -f "$SCRIPT_DIR/data/database.db" ]; then
    echo "📦 Initializing database..."
    mkdir -p "$SCRIPT_DIR/data"
    cd "$SCRIPT_DIR"
    python -c "from database import Database; db = Database('data/database.db'); db.construct()"
fi

# 启动后端
echo "🚀 Starting backend API on http://localhost:8000..."
cd "$SCRIPT_DIR/backend"
python main.py &
BACKEND_PID=$!

# 等待后端启动
sleep 2

# 启动前端
echo "🎨 Starting frontend on http://localhost:5173..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ PaperMap is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services."

# 捕获中断信号
trap "echo ''; echo '🛑 Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待进程
wait

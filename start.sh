#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

API_PORT=${API_PORT:-8855}
FE_PORT=${FE_PORT:-5173}

echo "================================"
echo "启动量化回测系统"
echo "后端端口: $API_PORT"
echo "前端端口: $FE_PORT"
echo "================================"

# 启动后端（后台）
echo "启动后端服务..."
(cd backend && bash start.sh) &
BACKEND_PID=$!

# 等待后端启动
sleep 5

# 启动前端
echo "启动前端服务..."
(cd frontend && API_PORT=$API_PORT PORT=$FE_PORT bash start.sh) &
FRONTEND_PID=$!

echo ""
echo "后端 PID: $BACKEND_PID"
echo "前端 PID: $FRONTEND_PID"
echo ""
echo "访问地址:"
echo "  前端: http://localhost:$FE_PORT"
echo "  后端 API: http://localhost:$API_PORT"
echo "  API 文档: http://localhost:$API_PORT/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

wait

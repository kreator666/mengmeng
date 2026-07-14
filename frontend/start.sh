#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

PORT=${PORT:-5173}
API_PORT=${API_PORT:-8855}

echo "启动前端开发服务器..."
echo "前端端口: $PORT"
echo "后端 API 端口: $API_PORT"

if [ ! -d "node_modules" ]; then
    echo "安装依赖..."
    npm install
fi

# 设置 API 代理目标
export VITE_API_BASE_URL="http://localhost:$API_PORT"

echo "启动 Vite..."
npm run dev -- --port "$PORT"

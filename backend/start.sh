#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

PORT=${PORT:-8855}
HOST=${HOST:-0.0.0.0}

echo "启动后端服务..."
echo "端口: $PORT"

if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python -m venv venv
fi

source venv/Scripts/activate

echo "安装/更新依赖..."
pip install -q -r requirements.txt

echo "启动 Uvicorn..."
uvicorn app.main:app --host "$HOST" --port "$PORT" --reload

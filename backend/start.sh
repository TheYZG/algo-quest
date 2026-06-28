#!/bin/bash
# 算法大陆后端启动脚本
# 用法: bash start.sh

set -e

echo "========================================="
echo "  Algorithm Continent - Backend Server"
echo "  AI Agent Coding Practice Platform"
echo "========================================="
echo ""

# Python 环境
PYTHON="/c/Users/21349/.workbuddy/binaries/python/envs/default/Scripts/python"
UVICORN="/c/Users/21349/.workbuddy/binaries/python/envs/default/Scripts/uvicorn"

cd "$(dirname "$0")"

# 检查 .env
if [ ! -f ".env" ]; then
    echo "[WARN] .env not found, copying from .env.example..."
    cp .env.example .env
    echo "[INFO] Edit .env to configure LLM_API_KEY!"
fi

# 检查 ChromaDB 是否有数据
echo ""
echo "[INFO] Checking ChromaDB status..."
$PYTHON -c "
from app.vectordb import get_collection_stats
stats = get_collection_stats()
print(f'ChromaDB problems: {stats[\"count\"]}')
if stats['count'] == 0:
    print('[WARN] Database is empty! Run import first:')
    print('       POST /api/admin/import')
" 2>/dev/null || echo "[WARN] First run, install deps then start"

echo ""
echo "[INFO] Starting FastAPI server..."
echo "       Docs: http://localhost:8000/api/docs"
echo "       Health: http://localhost:8000/api/health"
echo ""

$UVICORN app.main:app --host 0.0.0.0 --port 8000 --reload

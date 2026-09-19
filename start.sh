#!/usr/bin/env bash
# =============================================================================
# 船舶维修坞期管理平台 - 一键启动脚本
#
# 用法:
#   ./start.sh                # Docker 方式启动 (PostgreSQL + API + 前端)
#   ./start.sh docker         # 同上, 显式指定
#   ./start.sh dev            # 本地开发模式 (前端 Vite 热更新 + 后端 SQLite)
#   ./start.sh test           # 运行后端测试 (pytest)
#   ./start.sh down           # 停止并移除容器 (保留数据卷)
#   ./start.sh clean          # 停止并删除数据卷 (清空所有数据)
#   ./start.sh logs           # 查看容器日志
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

MODE="${1:-docker}"

# Pick docker compose v2 or legacy docker-compose.
compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "✗ 未找到 docker compose / docker-compose, 请先安装 Docker" >&2
    exit 1
  fi
}

start_docker() {
  echo "▶ 使用 Docker 启动船舶维修坞期管理平台..."
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "· 已根据 .env.example 创建 .env"
  fi
  compose_cmd up -d --build
  echo ""
  echo "▶ 等待 API 就绪..."
  for i in $(seq 1 30); do
    if curl -fsS http://localhost:"${API_PORT:-8000}"/health >/dev/null 2>&1; then
      echo "✔ 服务已启动:"
      echo "    前端页面 : http://localhost:${API_PORT:-8000}/"
      echo "    API 文档 : http://localhost:${API_PORT:-8000}/docs"
      echo "    健康检查 : http://localhost:${API_PORT:-8000}/health"
      echo ""
      echo "  停止: ./start.sh down   清空数据: ./start.sh clean   日志: ./start.sh logs"
      exit 0
    fi
    sleep 2
  done
  echo "✗ API 在 60 秒内未就绪, 请用 './start.sh logs' 查看日志" >&2
  compose_cmd logs --tail=50
  exit 1
}

start_dev() {
  echo "▶ 本地开发模式 (后端 SQLite + 前端 Vite 热更新)"

  # ---- backend ----
  if [ ! -d ".venv" ]; then
    echo "· 创建 Python 虚拟环境 .venv ..."
    python3 -m venv .venv 2>/dev/null || python3 -m venv --without-pip .venv
    if [ ! -x .venv/bin/pip ]; then
      curl -sSf https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
    fi
  fi
  .venv/bin/pip install -q -r backend/requirements.txt

  # ---- frontend ----
  if [ ! -d "frontend/node_modules" ]; then
    echo "· 安装前端依赖 ..."
    (cd frontend && npm install)
  fi

  echo "· 启动后端 http://localhost:8000 (SQLite, 自动写入演示数据)"
  (
    cd backend
    DATABASE_URL="sqlite:///./shipyard_dev.db" \
    SEED_ON_STARTUP=1 \
    ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  ) &
  API_PID=$!

  echo "· 启动前端 http://localhost:5173 (API 请求代理到 8000)"
  (cd frontend && npm run dev) &
  WEB_PID=$!

  trap 'kill $API_PID $WEB_PID 2>/dev/null || true' EXIT INT TERM
  wait
}

run_tests() {
  echo "▶ 运行后端测试..."
  if [ ! -d ".venv" ]; then
    python3 -m venv --without-pip .venv || python3 -m venv .venv
    if [ ! -x .venv/bin/pip ]; then
      curl -sSf https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
    fi
  fi
  .venv/bin/pip install -q -r backend/requirements.txt
  (
    cd backend
    DATABASE_URL="sqlite:///:memory:" ../.venv/bin/python -m pytest "$@"
  )
}

case "$MODE" in
  docker)
    start_docker
    ;;
  dev)
    start_dev
    ;;
  test)
    shift || true
    run_tests "$@"
    ;;
  down)
    compose_cmd down
    echo "✔ 容器已停止 (数据保留)"
    ;;
  clean)
    compose_cmd down -v
    echo "✔ 容器与数据卷已删除"
    ;;
  logs)
    compose_cmd logs -f
    ;;
  *)
    echo "用法: ./start.sh [docker|dev|test|down|clean|logs]" >&2
    exit 1
    ;;
esac

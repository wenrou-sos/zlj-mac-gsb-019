#!/usr/bin/env bash
# 船舶维修坞期管理平台 —— 一键启动
#
# 用法:
#   ./start.sh              使用 Docker Compose 启动（PostgreSQL + FastAPI + Vue/Nginx）
#   ./start.sh --local      本机直跑（无需 Docker；后端用 SQLite，前端用 Vite）
#   ./start.sh --test       运行后端测试
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-docker}"

# ---------------------------------------------------------------------------
run_tests() {
  echo "▶ 运行后端测试（SQLite，无需 PostgreSQL）..."
  cd backend
  run_pytest() {
    SHIPYARD_SEED_DEMO=0 "$1" -m pytest tests/ -v
  }
  if [ -x ".venv/bin/python" ] && .venv/bin/python -c "import fastapi, pytest" 2>/dev/null; then
    run_pytest .venv/bin/python
  elif python3 -c "import fastapi, pytest" 2>/dev/null; then
    run_pytest python3
  else
    echo "▶ 安装测试依赖到用户环境 ..."
    python3 -m pip install --user -q -r requirements.txt || pip3 install -q -r requirements.txt
    run_pytest python3
  fi
  cd ..
}

# ---------------------------------------------------------------------------
start_docker() {
  if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
  else
    echo "✘ 未检测到 Docker Compose，可改用 ./start.sh --local 以 SQLite 本地运行"
    exit 1
  fi
  echo "▶ 使用 $DC 构建并启动（db / backend / frontend）..."
  $DC up -d --build

  echo "▶ 等待后端健康检查..."
  for i in $(seq 1 30); do
    if curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
      echo "✔ 后端已就绪"
      break
    fi
    sleep 2
    [ "$i" = "30" ] && { echo "✘ 后端启动超时，请用 $DC logs backend 查看日志"; exit 1; }
  done

  cat <<'EOF'

============================================================
  🚢 船舶维修坞期管理平台已启动
  前端页面 : http://localhost:8080
  后端 API : http://localhost:8000  （文档 /docs）
  健康检查 : http://localhost:8000/api/health
  PostgreSQL: localhost:5432 (shipyard/shipyard)
  停止服务 : ./stop.sh
============================================================
EOF
}

# ---------------------------------------------------------------------------
start_local() {
  echo "▶ 本地模式：后端使用 SQLite，前端使用 Vite 开发服务器"
  cd backend
  python3 -m pip install --user -q -r requirements.txt 2>/dev/null || \
    pip3 install -q -r requirements.txt
  ( SHIPYARD_DATABASE_URL="sqlite:///./shipyard_local.db" \
    SHIPYARD_SEED_DEMO=1 \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 ) &
  BACK_PID=$!
  cd ../frontend
  [ -d node_modules ] || npm install --no-audit --no-fund
  VITE_API_TARGET=http://localhost:8000 npm run dev &
  FRONT_PID=$!
  trap "kill $BACK_PID $FRONT_PID 2>/dev/null || true" EXIT
  cat <<'EOF'

============================================================
  本地开发模式已启动
  前端页面 : http://localhost:5173
  后端 API : http://localhost:8000 （文档 /docs）
  按 Ctrl+C 停止
============================================================
EOF
  wait
}

case "$MODE" in
  --local|-l) start_local ;;
  --test|-t)  run_tests ;;
  docker)     start_docker ;;
  *) echo "未知参数: $MODE（支持: --local / --test）"; exit 1 ;;
esac

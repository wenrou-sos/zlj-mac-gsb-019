#!/usr/bin/env bash
# 停止船舶维修坞期管理平台的全部容器
set -euo pipefail
cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then
  docker compose down
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose down
else
  echo "未检测到 Docker Compose"
  exit 1
fi
echo "✔ 服务已停止（数据保留在 pgdata 卷中；如需清除: docker compose down -v）"

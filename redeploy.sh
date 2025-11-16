#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="mec.service"

echo "[Redeploy] 切换到 ${APP_DIR}"
cd "${APP_DIR}"

echo "[Redeploy] 拉取最新代码"
git fetch --all --prune
git reset --hard origin/main

echo "[Redeploy] 清理并安装前端依赖"
cd "${APP_DIR}/web_frontend"
rm -rf node_modules package-lock.json
npm install
echo "[Redeploy] 构建前端资源"
npm run build

echo "[Redeploy] 重启后端服务 ${SERVICE_NAME}"
cd "${APP_DIR}"
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-enabled --quiet "${SERVICE_NAME}"; then
    sudo systemctl restart "${SERVICE_NAME}"
  else
    echo "警告：服务 ${SERVICE_NAME} 未设置为 systemd 单元，请手动重启。" >&2
  fi
else
  echo "提示：当前环境没有 systemctl，请在服务器上手动重启 ${SERVICE_NAME}。" >&2
fi

echo "[Redeploy] 完成"

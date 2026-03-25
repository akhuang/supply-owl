#!/bin/bash
# Supply Owl 一键启动（Mac/Linux）
# 配置在 .env 文件中修改

set -e
cd "$(dirname "$0")"
export NO_PROXY=localhost,127.0.0.1

case "${1:-help}" in
  web)
    echo "[Owl] 启动 Web 仪表盘..."
    python3 -m uvicorn gateway.main:app --port 8000 --reload
    ;;
  tui)
    echo "[Owl] 启动 TUI..."
    cd hermes && python3 cli.py --toolsets memory,skills
    ;;
  both)
    echo "[Owl] 启动 Web 仪表盘 (后台)..."
    python3 -m uvicorn gateway.main:app --port 8000 &
    WEB_PID=$!
    echo "[Owl] Web PID=$WEB_PID → http://localhost:8000"
    echo ""
    echo "[Owl] 启动 TUI..."
    cd hermes && python3 cli.py --toolsets memory,skills
    echo "[Owl] 关闭 Web..."
    kill $WEB_PID 2>/dev/null
    ;;
  *)
    echo ""
    echo "  🦉 Supply Owl"
    echo ""
    echo "  用法:"
    echo "    ./run.sh web    启动 Web 仪表盘 (localhost:8000)"
    echo "    ./run.sh tui    启动 TUI 终端"
    echo "    ./run.sh both   同时启动 Web + TUI"
    echo ""
    echo "  配置: 修改 .env 文件"
    echo ""
    ;;
esac

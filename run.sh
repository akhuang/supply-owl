#!/bin/bash
# Supply Owl 一键启动（Mac/Linux）

set -e
cd "$(dirname "$0")"
export RUN_LAUNCHER_NAME=./run.sh
exec python3 run_launcher.py "$@"

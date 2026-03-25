@echo off
REM Supply Owl 一键启动（Windows）

cd /d "%~dp0"
set RUN_LAUNCHER_NAME=run.bat
python run_launcher.py %*

@echo off
REM Supply Owl 一键启动（Windows）
REM 配置在 .env 文件中修改

set NO_PROXY=localhost,127.0.0.1

if "%1"=="web" goto web
if "%1"=="tui" goto tui
if "%1"=="both" goto both

echo.
echo  🦉 Supply Owl
echo.
echo  用法:
echo    run.bat web    启动 Web 仪表盘 (localhost:8000)
echo    run.bat tui    启动 TUI 终端
echo    run.bat both   同时启动 Web + TUI
echo.
echo  配置: 修改 .env 文件
echo.
goto end

:web
echo [Owl] 启动 Web 仪表盘...
python -m uvicorn gateway.main:app --port 8000 --reload
goto end

:tui
echo [Owl] 启动 TUI...
cd hermes
python cli.py --toolsets memory,skills
cd ..
goto end

:both
echo [Owl] 启动 Web 仪表盘 (后台)...
start /B python -m uvicorn gateway.main:app --port 8000
echo [Owl] Web 已启动: http://localhost:8000
echo.
echo [Owl] 启动 TUI...
cd hermes
python cli.py --toolsets memory,skills
cd ..
goto end

:end

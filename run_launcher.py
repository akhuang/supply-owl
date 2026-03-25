#!/usr/bin/env python3
"""Project launcher that makes root .env authoritative for Web and TUI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
import yaml


def _load_project_cli_config(project_root: Path) -> dict:
    config_path = project_root / "cli-config.yaml"
    if not config_path.exists():
        return {}

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return config if isinstance(config, dict) else {}


def _write_hermes_config(project_root: Path, hermes_home: Path, env: dict[str, str]) -> None:
    config = _load_project_cli_config(project_root)

    model_config = config.get("model", {})
    if isinstance(model_config, str):
        model_config = {"default": model_config}
    elif not isinstance(model_config, dict):
        model_config = {}

    llm_model = env.get("LLM_MODEL", "").strip()
    llm_base_url = env.get("LLM_BASE_URL", "").strip()
    llm_api_key = env.get("LLM_API_KEY", "").strip()

    if llm_model:
        model_config["default"] = llm_model
    if llm_base_url:
        model_config["provider"] = "custom"
        model_config["base_url"] = llm_base_url
        env["OPENAI_BASE_URL"] = llm_base_url
    if llm_api_key:
        model_config["api_key"] = llm_api_key
        env["OPENAI_API_KEY"] = llm_api_key
    if llm_base_url or llm_api_key:
        env["HERMES_INFERENCE_PROVIDER"] = "custom"

    if model_config:
        config["model"] = model_config

    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def prepare_runtime_env(project_root: Path) -> dict[str, str]:
    """Load root .env into process env and mirror it to project-local Hermes home."""
    env_file = project_root / ".env"
    if not env_file.exists():
        raise FileNotFoundError(f"Missing .env: {env_file}")

    env = os.environ.copy()
    for key, value in dotenv_values(env_file).items():
        if value is not None:
            env[key] = value

    env.setdefault("NO_PROXY", "localhost,127.0.0.1")
    env.setdefault("no_proxy", env["NO_PROXY"])

    hermes_home = project_root / ".hermes"
    hermes_home.mkdir(exist_ok=True)
    (hermes_home / ".env").write_text(env_file.read_text(encoding="utf-8"), encoding="utf-8")
    _write_hermes_config(project_root, hermes_home, env)
    env["HERMES_HOME"] = str(hermes_home)
    return env


def run_web(project_root: Path, env: dict[str, str], *, reload: bool) -> int:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "gateway.main:app",
        "--port",
        "8000",
    ]
    if reload:
        command.append("--reload")
    print("[Owl] 启动 Web 仪表盘...")
    return subprocess.run(command, cwd=project_root, env=env).returncode


def run_tui(project_root: Path, env: dict[str, str]) -> int:
    command = [
        sys.executable,
        "cli.py",
        "--toolsets",
        "memory,skills",
    ]
    print("[Owl] 启动 TUI...")
    return subprocess.run(command, cwd=project_root / "hermes", env=env).returncode


def run_both(project_root: Path, env: dict[str, str]) -> int:
    web_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "gateway.main:app",
        "--port",
        "8000",
    ]
    print("[Owl] 启动 Web 仪表盘 (后台)...")
    web = subprocess.Popen(web_command, cwd=project_root, env=env)
    print(f"[Owl] Web PID={web.pid} -> http://localhost:8000")
    print("")
    try:
        return run_tui(project_root, env)
    finally:
        print("[Owl] 关闭 Web...")
        web.terminate()
        try:
            web.wait(timeout=5)
        except subprocess.TimeoutExpired:
            web.kill()
            web.wait(timeout=5)


def main(argv: list[str]) -> int:
    project_root = Path(__file__).resolve().parent
    env = prepare_runtime_env(project_root)

    mode = argv[1] if len(argv) > 1 else "help"
    if mode == "web":
        return run_web(project_root, env, reload=True)
    if mode == "tui":
        return run_tui(project_root, env)
    if mode == "both":
        return run_both(project_root, env)

    usage = os.environ.get("RUN_LAUNCHER_NAME") or (
        "run.bat" if os.name == "nt" else "./run.sh"
    )
    print("")
    print("  Supply Owl")
    print("")
    print("  用法:")
    print(f"    {usage} web    启动 Web 仪表盘 (localhost:8000)")
    print(f"    {usage} tui    启动 TUI 终端")
    print(f"    {usage} both   同时启动 Web + TUI")
    print("")
    print("  配置: 修改 .env 文件")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

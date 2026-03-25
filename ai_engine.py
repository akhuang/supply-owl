"""
Supply Owl AI 引擎 — Hermes AIAgent 的最薄封装

Web → gateway → ai_engine.chat() → Hermes → Ollama → 回复

配置从 .env 读取：
  LLM_MODEL=qwen3:32b
  LLM_BASE_URL=http://localhost:11434/v1
  LLM_API_KEY=ollama
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 加载 .env
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# 绕过系统代理
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

# 从 .env 读 LLM 配置
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:32b")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ollama")

# Hermes 路径
HERMES_DIR = Path(__file__).parent / "hermes"
AGENT_DIR = Path(__file__).parent / "agent"

# 懒加载的 agent 实例
_agent = None
_conversation_history: dict[str, list] = {}  # session_key → messages


def _get_agent():
    """懒加载 Hermes AIAgent"""
    global _agent
    if _agent is not None:
        return _agent

    sys.path.insert(0, str(HERMES_DIR))

    # Hermes 从 cwd 加载 SOUL.md
    original_cwd = os.getcwd()
    os.chdir(str(AGENT_DIR))

    try:
        from run_agent import AIAgent

        _agent = AIAgent(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            model=LLM_MODEL,
            quiet_mode=True,
            platform="web",
            enabled_toolsets=["memory"],
        )
    finally:
        os.chdir(original_cwd)

    logger.info("AIAgent initialized: model=%s base_url=%s", LLM_MODEL, LLM_BASE_URL)
    return _agent


async def chat(message: str, session_key: str = "web:default") -> str:
    """发送消息给 Hermes，返回回复。"""
    try:
        agent = _get_agent()
        history = _conversation_history.get(session_key, [])

        result = await asyncio.to_thread(
            agent.run_conversation,
            user_message=message,
            conversation_history=history,
        )

        _conversation_history[session_key] = result.get("messages", [])
        return result.get("final_response", "")

    except Exception as e:
        logger.error("ai_engine.chat failed: %s", e, exc_info=True)
        return f"AI 暂时不可用: {e}"

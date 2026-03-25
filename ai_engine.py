"""
Supply Owl AI 引擎 — Hermes AIAgent 的最薄封装

Web → gateway → ai_engine.chat() → Hermes → Ollama → 回复
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 绕过系统代理
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

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

    # 把 hermes 加入 Python path
    sys.path.insert(0, str(HERMES_DIR))

    # Hermes 会从 cwd 或 ~/.hermes/ 加载 SOUL.md 等文件
    # 设置 cwd 到 agent/ 目录让它找到 SOUL.md
    original_cwd = os.getcwd()
    os.chdir(str(AGENT_DIR))

    try:
        from run_agent import AIAgent

        _agent = AIAgent(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model=os.environ.get("LLM_MODEL", "qwen2.5:14b"),
            quiet_mode=True,
            platform="web",
        )
    finally:
        os.chdir(original_cwd)

    return _agent


async def chat(message: str, session_key: str = "web:default") -> str:
    """发送消息给 Hermes，返回回复。

    Args:
        message: 用户输入
        session_key: 会话标识，同一个 key 共享上下文

    Returns:
        Owl 的回复文本
    """
    try:
        agent = _get_agent()

        # 获取会话历史
        history = _conversation_history.get(session_key, [])

        # run_conversation 是同步的，放到线程池跑
        result = await asyncio.to_thread(
            agent.run_conversation,
            user_message=message,
            conversation_history=history,
        )

        # 更新会话历史
        _conversation_history[session_key] = result.get("messages", [])

        return result.get("final_response", "")

    except Exception as e:
        logger.error("ai_engine.chat failed: %s", e, exc_info=True)
        return f"AI 暂时不可用: {e}"

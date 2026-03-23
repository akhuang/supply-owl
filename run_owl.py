"""
Supply Owl — 用 Hermes AIAgent 引擎跑

带上 Hermes 的全部小模型优化：
- 冻结快照 (SOUL.md/MEMORY.md/USER.md)
- 技能渐进加载
- 上下文压缩
"""

# Patch httpx for Ollama compatibility — MUST be first
import ollama_patch

import os
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OPENAI_API_KEY", "ollama")

from hermes.run_agent import AIAgent

def create_owl():
    agent = AIAgent(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        provider="openrouter",  # Hermes maps "custom" to "openrouter"
        api_mode="chat_completions",
        model="qwen2.5:7b",
        max_iterations=10,
        skip_memory=False,
        skip_context_files=False,
        quiet_mode=True,
        verbose_logging=False,
        enabled_toolsets={"memory", "skills"},  # Only memory + skills, no terminal/web
        session_id=None,
        platform="api",
    )
    return agent

if __name__ == "__main__":
    print("🦉 Starting Supply Owl with Hermes Engine...")
    owl = create_owl()
    print(f"  Model: {owl.model}")
    print(f"  Provider: {owl.provider}")
    print(f"  Memory: enabled")
    print()

    # Test conversation
    messages = [{"role": "user", "content": "你是谁？一句话"}]
    try:
        result = owl.run_conversation(messages=messages)
        # result is a dict with 'messages', 'usage', etc.
        if isinstance(result, dict):
            for msg in result.get("messages", []):
                if msg.get("role") == "assistant":
                    print(f"🦉 {msg.get('content', '')[:300]}")
        else:
            print(f"🦉 {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

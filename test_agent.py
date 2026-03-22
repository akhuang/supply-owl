"""
Supply Owl — 最小化测试
直接用 httpx 调 Ollama，验证 SOUL.md + MEMORY.md 的业务理解。
"""

import json
import urllib.request
import re
import time

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:4b"

# 读取 SOUL.md 和 MEMORY.md
with open("agent/SOUL.md", "r") as f:
    soul = f.read()
with open("agent/MEMORY.md", "r") as f:
    memory = f.read()

system_prompt = f"{soul}\n\n---\n决策原则:\n{memory}"

def ask(messages, model=MODEL):
    data = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": 4096}
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    content = result.get("message", {}).get("content", "")
    if "<think>" in content:
        content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)
    return content.strip()

print("=" * 50)
print("🦉 Supply Owl — 最小化测试")
print(f"Model: {MODEL} via Ollama")
print("=" * 50)

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "你好，一句话介绍你自己"}
]

print("\n> 你好，一句话介绍你自己\n")
a1 = ask(messages)
if a1:
    print(f"🦉 {a1}")
    messages.append({"role": "assistant", "content": a1})

    # 测试业务理解
    print("\n" + "-" * 50)
    q2 = "合同 1Y01052508474L 的批次 HWC0044Q 还没有 CPD，供应经理张三刚在 WeLink 催了，我该怎么办？"
    messages.append({"role": "user", "content": q2})
    print(f"\n> {q2}\n")
    a2 = ask(messages)
    if a2:
        print(f"🦉 {a2}")

print("\n" + "=" * 50)
print("测试完成")

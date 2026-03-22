"""
Supply Owl — API Gateway
FastAPI 薄层，桥接 Web UI 和 Hermes Agent。
"""

import json
import re
import os
import urllib.request
from pathlib import Path
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Supply Owl Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Config ==========
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.getenv("OWL_MODEL", "qwen3:4b")
PROJECT_ROOT = Path(__file__).parent.parent

# Load SOUL.md + MEMORY.md as system prompt
def load_system_prompt():
    parts = []
    for name in ["SOUL.md", "USER.md", "MEMORY.md"]:
        p = PROJECT_ROOT / "agent" / name
        if p.exists():
            parts.append(p.read_text())
    return "\n\n---\n\n".join(parts)

SYSTEM_PROMPT = load_system_prompt()


# ========== Ollama Client ==========
def chat(messages, model=MODEL):
    """Call Ollama native API"""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_ctx": 4096}
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    content = result.get("message", {}).get("content", "")
    # Strip qwen3 thinking tags
    if "<think>" in content:
        content = re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)
    return content.strip()


# ========== Models ==========
class Fragment(BaseModel):
    contract: str
    source: str
    context: Optional[str] = None
    sender: Optional[str] = None
    timestamp: Optional[int] = None

class ChatMessage(BaseModel):
    message: str


# ========== Routes ==========

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Supply Owl</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#F0F1F3;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#111}
.container{max-width:600px;width:100%;padding:20px}
h1{font-size:24px;margin-bottom:4px}
.sub{color:#6B6F76;font-size:14px;margin-bottom:24px}
.chat-box{background:#FFF;border:1px solid #D5D8DC;border-radius:3px;min-height:300px;max-height:500px;overflow-y:auto;padding:16px;margin-bottom:12px;font-size:13px;line-height:1.6}
.msg{margin-bottom:12px;padding:8px 12px;border-radius:3px}
.msg.user{background:#F0F1F3;text-align:right}
.msg.owl{background:#FAF6F0;border:1px solid #EDE6DA}
.msg .label{font-size:11px;color:#A0A4AB;margin-bottom:2px}
.input-row{display:flex;gap:8px}
input{flex:1;padding:10px 12px;border:1px solid #D5D8DC;border-radius:3px;font-size:13px;outline:none}
input:focus{border-color:#999}
button{padding:10px 20px;background:#111;color:#FFF;border:none;border-radius:3px;font-size:13px;font-weight:600;cursor:pointer}
button:hover{background:#333}
button:disabled{opacity:0.4;cursor:not-allowed}
.status{font-size:11px;color:#A0A4AB;margin-top:8px;text-align:center}
</style></head>
<body>
<div class="container">
<h1>🦉 Supply Owl</h1>
<div class="sub">你的夜行分身 · 试试问合同相关的问题</div>
<div class="chat-box" id="chatBox"></div>
<div class="input-row">
<input id="input" placeholder="输入问题... 例如: 合同 1Y01052508474L 的 HWC0044Q 没承诺怎么办" autofocus>
<button id="btn" onclick="send()">发送</button>
</div>
<div class="status" id="status">Model: """ + MODEL + """ via Ollama</div>
</div>
<script>
const chatBox = document.getElementById('chatBox');
const input = document.getElementById('input');
const btn = document.getElementById('btn');
const status = document.getElementById('status');

function addMsg(role, text) {
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  d.innerHTML = '<div class="label">' + (role === 'user' ? '你' : '🦉 Owl') + '</div>' + text.replace(/\\n/g, '<br>');
  chatBox.appendChild(d);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function send() {
  const msg = input.value.trim();
  if (!msg) return;
  addMsg('user', msg);
  input.value = '';
  btn.disabled = true;
  status.textContent = '思考中...';
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg})
    });
    const data = await r.json();
    addMsg('owl', data.reply || data.error || '无回复');
  } catch(e) {
    addMsg('owl', '请求失败: ' + e.message);
  }
  btn.disabled = false;
  status.textContent = 'Model: """ + MODEL + """ via Ollama';
  input.focus();
}

input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
</script>
</body></html>"""


@app.post("/api/chat")
async def api_chat(msg: ChatMessage):
    """简单对话接口"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": msg.message}
    ]
    try:
        reply = chat(messages)
        return {"reply": reply}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "supply-owl", "model": MODEL}


@app.post("/api/fragment")
async def receive_fragment(fragment: Fragment):
    """接收碎片推送"""
    return {"received": True, "contract": fragment.contract}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8321)

"""
Supply Owl — API Gateway
FastAPI 薄层，桥接 Web UI 和 Hermes Agent。
"""

import json
import re
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")  # NO_PROXY, OPENAI_*

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List

from hermes.run_agent import AIAgent

app = FastAPI(title="Supply Owl Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Config ==========
MODEL = os.getenv("OWL_MODEL", "qwen2.5:14b")
BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("OPENAI_API_KEY", "ollama")

# ========== Hermes AIAgent ==========
_owl = None

def get_owl() -> AIAgent:
    """Lazy-init Hermes AIAgent (singleton)"""
    global _owl
    if _owl is None:
        _owl = AIAgent(
            base_url=BASE_URL,
            api_key=API_KEY,
            provider="openrouter",
            api_mode="chat_completions",
            model=MODEL,
            max_iterations=10,
            quiet_mode=True,
            verbose_logging=False,
            enabled_toolsets={"memory", "skills"},
            platform="api",
        )
    return _owl

def chat_with_hermes(user_message: str) -> str:
    """Run one conversation turn through Hermes AIAgent"""
    owl = get_owl()
    result = owl.run_conversation(user_message=user_message)
    if isinstance(result, dict):
        return result.get("final_response", str(result))
    return str(result)


# ========== supply-cli ==========
CONTRACT_RE = re.compile(r'\b(1Y0[A-Za-z0-9]{11}|00E[A-Za-z0-9]{11})\b')
BATCH_RE = re.compile(r'\b(HW[A-Z]\d{3,5}[A-Z])\b')

def find_contracts(text: str) -> List[str]:
    return list(set(CONTRACT_RE.findall(text.upper())))

def find_batches(text: str) -> List[str]:
    return list(set(BATCH_RE.findall(text.upper())))

def supply_cli(cmd: str, *args) -> dict:
    """Call supply-cli and return parsed JSON"""
    try:
        result = subprocess.run(
            ["supply-cli", cmd, *args],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return {"error": result.stderr.strip() or "empty response"}
    except subprocess.TimeoutExpired:
        return {"error": "supply-cli timeout"}
    except Exception as e:
        return {"error": str(e)}

def enrich_context(user_message: str) -> str:
    """Detect contract numbers in message, auto-query supply-cli, return enriched context"""
    contracts = find_contracts(user_message)
    if not contracts:
        return ""

    parts = []
    for cno in contracts[:5]:  # max 5 contracts per query
        data = supply_cli("detail", cno)
        if data.get("found"):
            batches_info = []
            for b in data.get("batches", []):
                cpd = b.get("cpd") or "未承诺"
                rpd = b.get("rpd") or "无"
                apd = b.get("apd") or "未交单"
                status = b.get("demandStatus", "")
                urgent = "急单" if b.get("urgentFlag") == "Y" else ""
                batch_no = b.get("batchNo", "?")

                # CPD vs RPD judgment
                if cpd == "未承诺":
                    risk = "CPD未承诺"
                elif cpd > rpd and rpd != "无":
                    risk = f"CPD不满足RPD(差{_days_diff(rpd, cpd)}天)"
                else:
                    risk = "CPD满足RPD"

                line = f"  {batch_no}: CPD={cpd} RPD={rpd} APD={apd} {risk} {urgent} {status}".strip()
                batches_info.append(line)

            parts.append(
                f"合同 {cno} ({data.get('projectName','')}/{data.get('customer','')}):\n"
                + "\n".join(batches_info)
            )
        else:
            parts.append(f"合同 {cno}: 未找到数据")

    # Also check anomalies
    for cno in contracts[:3]:
        anomaly = supply_cli("anomalies", cno)
        if anomaly.get("anomalies"):
            parts.append(f"合同 {cno} 异常: {json.dumps(anomaly['anomalies'], ensure_ascii=False)}")

    return "\n\n".join(parts)

def _days_diff(date1: str, date2: str) -> int:
    """Simple date diff in days"""
    try:
        from datetime import datetime
        d1 = datetime.strptime(date1, "%Y-%m-%d")
        d2 = datetime.strptime(date2, "%Y-%m-%d")
        return abs((d2 - d1).days)
    except:
        return 0


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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--sans:'IBM Plex Sans',-apple-system,sans-serif;--mono:'IBM Plex Mono','SF Mono',monospace;--bg:#FAFAFA;--card:#FFF;--border:#DDD;--border-light:#EEE;--ink1:#1A1A1A;--ink2:#555;--ink3:#888;--ink4:#AAA;--owl-bg:#FAF6F0;--owl-border:#EDE6DA;--green:#2D7A3F;--red:#C7352B;--amber:#B8860B}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--sans);background:#E8E8E8;color:var(--ink1);-webkit-font-smoothing:antialiased;display:flex;justify-content:center;min-height:100vh;padding:24px}
.shell{width:100%;max-width:720px;display:flex;flex-direction:column;gap:0}
.header{padding:16px 0 12px;display:flex;align-items:center;gap:12px}
.header h1{font-size:18px;font-weight:700}
.header .sub{font-size:12px;color:var(--ink3);margin-left:auto;font-family:var(--mono)}
.chat{flex:1;background:var(--card);border:1px solid var(--border);display:flex;flex-direction:column;min-height:500px;max-height:calc(100vh - 140px)}
.chat-body{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.chat-body::-webkit-scrollbar{width:3px}
.chat-body::-webkit-scrollbar-thumb{background:var(--border)}
.msg{max-width:90%;font-size:13px;line-height:1.7}
.msg.user{align-self:flex-end;background:var(--bg);border:1px solid var(--border-light);padding:8px 14px}
.msg.owl{align-self:flex-start;background:var(--owl-bg);border:1px solid var(--owl-border);padding:10px 14px}
.msg-head{display:flex;align-items:center;gap:6px;margin-bottom:4px;font-size:11px;color:var(--ink4);font-family:var(--mono)}
.msg-head .elapsed{margin-left:auto;color:var(--ink4)}
.msg-head .source{color:var(--green);font-weight:600}
.msg-body p{margin:0 0 8px}
.msg-body p:last-child{margin:0}
.msg-body strong{font-weight:700;color:var(--ink1)}
.msg-body ul,.msg-body ol{margin:4px 0 8px 18px}
.msg-body li{margin:2px 0}
.msg-body code{font-family:var(--mono);font-size:12px;background:rgba(0,0,0,0.05);padding:1px 4px}
.msg-body h3{font-size:13px;font-weight:700;margin:8px 0 4px}
.msg-body table{border-collapse:collapse;font-size:12px;margin:6px 0}
.msg-body th,.msg-body td{border:1px solid var(--border-light);padding:3px 8px;text-align:left}
.msg-body th{background:var(--bg);font-weight:600;font-size:11px}
.msg-body blockquote{border-left:3px solid var(--owl-border);padding:4px 10px;margin:6px 0;color:var(--ink2);font-size:12px}
.msg-body hr{border:none;border-top:1px solid var(--border-light);margin:8px 0}
.chat-input{border-top:1px solid var(--border);display:flex;align-items:center;padding:0}
.chat-input input{flex:1;border:none;outline:none;padding:12px 16px;font-family:var(--sans);font-size:13px;color:var(--ink1);background:transparent}
.chat-input input::placeholder{color:var(--ink4)}
.chat-input button{padding:12px 20px;background:var(--ink1);color:#FFF;border:none;font-family:var(--sans);font-size:12px;font-weight:700;cursor:pointer;letter-spacing:0.02em}
.chat-input button:hover{background:#333}
.chat-input button:disabled{opacity:0.3;cursor:not-allowed}
.footer{padding:6px 0;display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--ink4);letter-spacing:0.02em}
.presets{display:flex;gap:6px;padding:8px 16px;background:var(--bg);border-top:1px solid var(--border-light);flex-wrap:wrap}
.preset{font-family:var(--sans);font-size:11px;padding:4px 10px;border:1px solid var(--border);background:var(--card);color:var(--ink2);cursor:pointer}
.preset:hover{border-color:var(--ink3);color:var(--ink1)}
</style></head>
<body>
<div class="shell">
<div class="header">
<h1>🦉 Supply Owl</h1>
<span class="sub">""" + MODEL + """ · Hermes Engine</span>
</div>
<div class="chat">
<div class="chat-body" id="chatBody">
<div class="msg owl">
<div class="msg-head">🦉 owl</div>
<div class="msg-body"><p>我是 Owl，帮你盯合同、催承诺、提拉跟进的。直接给我合同号就行。</p></div>
</div>
</div>
<div class="presets">
<button class="preset" onclick="ask('合同 1Y01052508474L 什么情况')">1Y01052508474L 什么情况</button>
<button class="preset" onclick="ask('1Y02893760876C 需要提拉')">1Y02893760876C 提拉</button>
<button class="preset" onclick="ask('1Y04567891234D 的 HWL0007S 怎么处理')">HWL0007S 怎么处理</button>
</div>
<div class="chat-input">
<input id="input" placeholder="合同号、批次号、或任何问题..." autofocus>
<button id="btn" onclick="send()">发送</button>
</div>
</div>
<div class="footer">
<span>supply-cli connected</span>
<span id="lastElapsed"></span>
</div>
</div>
<script>
const body=document.getElementById('chatBody'),chatInput=document.getElementById('input'),btn=document.getElementById('btn');

function md(text){
  return text
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/`([^`]+)`/g,'<code>$1</code>')
    .replace(/^[-*] (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s,function(m){return '<ul>'+m+'</ul>'})
    .replace(/^> (.+)$/gm,'<blockquote>$1</blockquote>')
    .replace(/^---$/gm,'<hr>')
    .replace(/\\n\\n/g,'</p><p>')
    .replace(/\\n/g,'<br>')
    .replace(/^/,'<p>').replace(/$/,'</p>')
    .replace(/<p><h3>/g,'<h3>').replace(/<\/h3><\/p>/g,'</h3>')
    .replace(/<p><ul>/g,'<ul>').replace(/<\/ul><\/p>/g,'</ul>')
    .replace(/<p><hr><\/p>/g,'<hr>')
    .replace(/<p><blockquote>/g,'<blockquote>').replace(/<\/blockquote><\/p>/g,'</blockquote>')
    .replace(/<p><\/p>/g,'');
}

function addMsg(role,html,meta){
  const d=document.createElement('div');d.className='msg '+role;
  let head='<div class="msg-head">';
  if(role==='user') head+='你';
  else{
    head+='🦉 owl';
    if(meta?.source) head+=' <span class="source">'+meta.source+'</span>';
    if(meta?.elapsed) head+='<span class="elapsed">'+meta.elapsed+'</span>';
  }
  head+='</div>';
  d.innerHTML=head+'<div class="msg-body">'+(role==='user'?html:md(html))+'</div>';
  body.appendChild(d);
  body.scrollTop=body.scrollHeight;
}

function ask(msg){
  addMsg('user',msg);
  btn.disabled=true;
  document.querySelectorAll('.preset').forEach(function(b){b.disabled=true});
  showLoading();
  var t0=Date.now();
  fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg}),signal:AbortSignal.timeout(180000)})
  .then(function(r){return r.json()})
  .then(function(data){
    if(loading)loading.remove();
    var elapsed=((Date.now()-t0)/1000).toFixed(1)+'s';
    document.getElementById('lastElapsed').textContent='last: '+elapsed;
    var meta={elapsed:elapsed};
    if(data.data_source) meta.source='via '+data.data_source;
    addMsg('owl',data.reply||data.error||'无回复',meta);
    btn.disabled=false;
    document.querySelectorAll('.preset').forEach(function(b){b.disabled=false});
    chatInput.focus();
  })
  .catch(function(e){if(loading)loading.remove();addMsg('owl','请求失败: '+e.message);btn.disabled=false;document.querySelectorAll('.preset').forEach(function(b){b.disabled=false})});
}

let loading=null;
function showLoading(){
  loading=document.createElement('div');loading.className='msg owl';
  loading.innerHTML='<div class="msg-head">🦉 owl</div><div class="msg-body" style="color:var(--ink3)">查数据 + 思考中... (CPU模式约30-60秒)</div>';
  loading.id='loading-msg';
  body.appendChild(loading);body.scrollTop=body.scrollHeight;
}

async function send(){
  const msg=chatInput.value.trim();if(!msg)return;
  addMsg('user',msg);chatInput.value='';btn.disabled=true;
  document.querySelectorAll('.preset').forEach(b=>b.disabled=true);
  showLoading();
  const t0=Date.now();
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg}),signal:AbortSignal.timeout(180000)});
    const data=await r.json();
    if(loading)loading.remove();
    const elapsed=((Date.now()-t0)/1000).toFixed(1)+'s';
    document.getElementById('lastElapsed').textContent='last: '+elapsed;
    const meta={elapsed};
    if(data.data_source) meta.source='via '+data.data_source;
    addMsg('owl',data.reply||data.error||'无回复',meta);
  }catch(e){if(loading)loading.remove();addMsg('owl','请求失败: '+e.message)}
  btn.disabled=false;
  document.querySelectorAll('.preset').forEach(b=>b.disabled=false);
  chatInput.focus();
}

chatInput.addEventListener('keydown',e=>{if(e.key==='Enter')send()});
</script>
</body></html>"""


@app.post("/api/chat")
async def api_chat(msg: ChatMessage):
    """对话接口 — Hermes AIAgent 引擎 + supply-cli 数据充实"""
    # Auto-enrich: detect contract numbers → query supply-cli
    context = enrich_context(msg.message)
    enriched_contracts = find_contracts(msg.message)

    user_content = msg.message
    if context:
        user_content = f"{msg.message}\n\n---\n以下是系统自动查询到的数据（来自 supply-cli）:\n{context}"

    try:
        reply = chat_with_hermes(user_content)
        return {
            "reply": reply,
            "enriched": enriched_contracts,
            "data_source": "supply-cli" if context else None
        }
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

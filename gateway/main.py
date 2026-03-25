"""
Supply Owl — API Gateway
仪表盘后端：SQLite 数据层 + 代码做判断 + 返回结构化 JSON
"""

import json
import re
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from datastore import OwlDB
from datastore.queries import (
    analyze_contract as ds_analyze_contract,
    build_dashboard as ds_build_dashboard,
    get_full_picture,
    add_progress,
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="Supply Owl Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (dashboard HTML)
STATIC_DIR = Path(__file__).parent / "static"


# ========== SQLite 消息状态 ==========
DB_PATH = Path(__file__).parent / "messages.db"

def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def _init_db():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            contracts TEXT NOT NULL,
            batches TEXT NOT NULL,
            draft_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            reply_text TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

_init_db()

# 合同数据层
OWL_DB_PATH = os.environ.get("OWL_DB_PATH", str(Path(__file__).parent.parent / "owl.db"))
owl_db = OwlDB(OWL_DB_PATH)

# ========== store.json 自动同步 ==========

import threading
import time as _time

STORE_JSON_PATH = os.environ.get("STORE_JSON_PATH", "~/.supply-cli/store.json")
_store_path = Path(STORE_JSON_PATH).expanduser()
_last_mtime: float = 0


def _sync_if_changed():
    """检查 store.json 是否有变化，有则自动导入"""
    global _last_mtime
    if not _store_path.exists():
        return
    mtime = _store_path.stat().st_mtime
    if mtime > _last_mtime:
        try:
            stats = owl_db.import_snapshot(str(_store_path))
            _last_mtime = mtime
            print(f"[Owl] store.json 已同步: {stats['batches']} batches, {stats['cases']} cases")
        except Exception as e:
            print(f"[Owl] store.json 同步失败: {e}")


def _watch_store_json():
    """后台线程，每 10 秒检查一次 store.json"""
    while True:
        _sync_if_changed()
        _time.sleep(10)


# 启动时立即同步一次
_sync_if_changed()

# 后台持续监听
_watcher = threading.Thread(target=_watch_store_json, daemon=True)
_watcher.start()

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ========== 合同号匹配 ==========
CONTRACT_RE = re.compile(r'\b(1Y0[A-Za-z0-9]{11}|00E[A-Za-z0-9]{11})\b')

# ========== 核心: 通过 datastore 读取层 ==========

def analyze_contract(contract_no: str) -> dict:
    return ds_analyze_contract(owl_db, contract_no)

def build_dashboard() -> dict:
    data = ds_build_dashboard(owl_db)
    # 兼容前端已有的 stats 字段名
    return {
        "stats": {
            "red": data["red"],
            "yellow": data["yellow"],
            "green": data["green"],
            "total": data["total_contracts"],
        },
        "alert_groups": data["alert_groups"],
        "contracts": data["contracts"],
    }


# ========== 草稿生成 ==========

DRAFT_TEMPLATES = {
    "承诺坐席": "请协助确认以下批次的承诺日期：\n{batch_lines}\n请尽快回复承诺时间，谢谢。",
    "大调度": "以下批次CPD不满足RPD，需要提拉：\n{batch_lines}\n请协调资源，目标拉到RPD之前。",
    "提拉座席": "以下批次需要提拉处理：\n{batch_lines}\n请安排提拉，谢谢。",
}

def generate_draft(role: str, contracts: list, batches: list) -> str:
    lines = []
    for b in batches:
        contract = b.get("contract", "")
        batch_id = b.get("batch", "")
        rpd = b.get("rpd", "")
        cpd = b.get("cpd", "未承诺")
        if role == "承诺坐席":
            lines.append(f"  - {contract} / {batch_id}，RPD {rpd}，当前未承诺")
        else:
            lines.append(f"  - {contract} / {batch_id}，RPD {rpd}，CPD {cpd}")
    template = DRAFT_TEMPLATES.get(role, DRAFT_TEMPLATES["提拉座席"])
    return template.format(batch_lines="\n".join(lines))


# ========== Models ==========

class Fragment(BaseModel):
    contract: str
    source: str
    context: Optional[str] = None
    sender: Optional[str] = None

class DraftRequest(BaseModel):
    role: str
    contracts: List[dict]
    batches: List[dict]

class SendRequest(BaseModel):
    role: str
    action: str
    contracts: List[str]
    batches: List[dict]
    draft_text: str

class ReplyRequest(BaseModel):
    reply_text: str

class MessageStatusUpdate(BaseModel):
    status: str


# ========== Routes ==========

@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "supply-owl"}

@app.get("/api/dashboard")
def dashboard():
    """仪表盘数据 — 代码做完所有判断，前端只渲染"""
    return build_dashboard()

@app.get("/api/contracts/{contract_id}")
def get_contract(contract_id: str):
    """单合同详情"""
    return analyze_contract(contract_id.upper())

@app.get("/api/contracts/{contract_id}/full")
def get_contract_full(contract_id: str):
    """合同全貌 = 状态 + 进展记录"""
    return get_full_picture(owl_db, contract_id.upper())

@app.post("/api/fragment")
async def receive_fragment(fragment: Fragment):
    """接收碎片 → 录入进展记录"""
    contract = fragment.contract.upper()
    add_progress(
        owl_db, contract,
        contact=fragment.sender or fragment.source,
        content=fragment.context or "",
    )
    return {"received": True, "contract": contract}

# ========== AI Chat (Hermes AIAgent) ==========

class ChatRequest(BaseModel):
    message: str
    session: str = "web:default"


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """AI 对话 — Hermes AIAgent，带 SOUL 人设"""
    from ai_engine import chat
    reply = await chat(req.message, session_key=req.session)
    return {"reply": reply}


@app.post("/api/sync")
def sync_snapshot(snapshot_path: str = ""):
    """从 supply-cli store.json 同步数据到 SQLite

    默认读 .env 里的 STORE_JSON_PATH（~/.supply-cli/store.json）
    也可以传 snapshot_path 参数指定其他文件
    """
    if not snapshot_path:
        snapshot_path = os.environ.get("STORE_JSON_PATH", "")
    if snapshot_path:
        snapshot_path = str(Path(snapshot_path).expanduser())
    if not snapshot_path or not Path(snapshot_path).exists():
        return {"error": "store.json 不存在", "path": snapshot_path,
                "hint": "请先运行 supply-cli fetch，或在 .env 中设置 STORE_JSON_PATH"}
    stats = owl_db.import_snapshot(snapshot_path)
    return {"synced": True, **stats}


# ========== 消息 API ==========

@app.post("/api/draft")
def create_draft(req: DraftRequest):
    """生成草稿文本"""
    text = generate_draft(req.role, req.contracts, req.batches)
    return {"draft": text}

@app.post("/api/messages")
def send_message(req: SendRequest):
    """发送消息 → 状态变为 waiting"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO messages (role, action, contracts, batches, draft_text, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'waiting', ?, ?)""",
        (req.role, req.action, json.dumps(req.contracts), json.dumps(req.batches),
         req.draft_text, now, now)
    )
    msg_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": msg_id, "status": "waiting"}

@app.get("/api/messages")
def list_messages(status: Optional[str] = None):
    """列出消息 — 可按 status 过滤 (waiting / replied / processed)"""
    conn = _get_db()
    if status:
        rows = conn.execute(
            "SELECT * FROM messages WHERE status = ? ORDER BY updated_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY updated_at DESC"
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

@app.put("/api/messages/{msg_id}")
def update_message(msg_id: int, req: MessageStatusUpdate):
    """更新消息状态"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_db()
    conn.execute(
        "UPDATE messages SET status = ?, updated_at = ? WHERE id = ?",
        (req.status, now, msg_id)
    )
    conn.commit()
    conn.close()
    return {"id": msg_id, "status": req.status}

@app.put("/api/messages/{msg_id}/reply")
def reply_message(msg_id: int, req: ReplyRequest):
    """收到回复 — 状态变为 replied"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_db()
    conn.execute(
        "UPDATE messages SET status = 'replied', reply_text = ?, updated_at = ? WHERE id = ?",
        (req.reply_text, now, msg_id)
    )
    conn.commit()
    conn.close()
    return {"id": msg_id, "status": "replied"}

def _row_to_dict(row):
    d = dict(row)
    d["contracts"] = json.loads(d["contracts"])
    d["batches"] = json.loads(d["batches"])
    return d

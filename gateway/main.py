"""
Supply Owl — API Gateway
仪表盘后端：supply-cli 查数据 + 代码做判断 + 返回结构化 JSON
"""

import json
import re
import os
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

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

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ========== supply-cli ==========
CONTRACT_RE = re.compile(r'\b(1Y0[A-Za-z0-9]{11}|00E[A-Za-z0-9]{11})\b')

def supply_cli(cmd: str, *args) -> dict:
    try:
        result = subprocess.run(
            ["supply-cli", cmd, *args],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return {"error": result.stderr.strip() or "empty response"}
    except Exception as e:
        return {"error": str(e)}

def _days_diff(d1: str, d2: str) -> int:
    try:
        return abs((datetime.strptime(d2, "%Y-%m-%d") - datetime.strptime(d1, "%Y-%m-%d")).days)
    except:
        return 0


# ========== 核心: 代码做判断 ==========

def analyze_batch(b: dict, contract_no: str) -> dict:
    """单个批次的判断 — 纯代码，不过模型"""
    batch_no = b.get("batchNo", "?")
    cpd = b.get("cpd")
    rpd = b.get("rpd", "")
    apd = b.get("apd")
    urgent = b.get("urgentFlag") == "Y"
    kit = b.get("kitStatus", "")
    related = b.get("relatedContractNo")
    today = datetime.now().strftime("%Y-%m-%d")

    # CPD vs RPD
    if not cpd:
        status = "uncommitted"
        risk_label = "未承诺"
        contact_role = "承诺坐席"
        contact_reason = "未承诺 → 承诺坐席"
        via_contract = contract_no
    elif rpd and cpd > rpd:
        gap = _days_diff(rpd, cpd)
        status = "not_met"
        risk_label = f"不满足(差{gap}天)"
        # 路由: 找谁
        if batch_no.startswith("HWA"):
            contact_role = "大调度"
            contact_reason = f"HWA开头 → 直接用1Y0找大调度"
            via_contract = contract_no
        elif related:
            contact_role = "大调度"
            contact_reason = f"有关联00E → 用{related}找大调度"
            via_contract = related
        else:
            contact_role = "提拉座席"
            contact_reason = "非HWA+无00E → 提拉座席"
            via_contract = contract_no
    else:
        status = "met"
        risk_label = "满足"
        contact_role = None
        contact_reason = None
        via_contract = None

    # 提拉目标
    pull_target = rpd if status == "not_met" else None

    return {
        "batch": batch_no,
        "cpd": cpd,
        "rpd": rpd,
        "apd": apd,
        "status": status,
        "risk_label": risk_label,
        "urgent": urgent,
        "kit": kit,
        "contact_role": contact_role,
        "contact_reason": contact_reason,
        "via_contract": via_contract,
        "pull_target": pull_target,
    }


def analyze_contract(contract_no: str) -> dict:
    """合同级分析"""
    data = supply_cli("detail", contract_no)
    if not data.get("found"):
        return {"contract": contract_no, "found": False}

    batches = [analyze_batch(b, contract_no) for b in data.get("batches", [])]

    # 合同温度 = 最高批次温度
    if any(b["status"] == "not_met" and b["urgent"] for b in batches):
        temperature = "red"
    elif any(b["status"] == "not_met" for b in batches):
        temperature = "yellow"
    elif any(b["status"] == "uncommitted" for b in batches):
        temperature = "yellow"
    else:
        temperature = "green"

    return {
        "contract": contract_no,
        "found": True,
        "project": data.get("projectName", ""),
        "customer": data.get("customer", ""),
        "temperature": temperature,
        "batches": batches,
    }


def build_dashboard() -> dict:
    """构建完整仪表盘数据 — 按联系人分组"""
    # 查所有活跃合同
    all_data = supply_cli("search", "1Y0")
    contracts = []
    if isinstance(all_data, dict) and all_data.get("matches"):
        for m in all_data["matches"]:
            cno = m.get("contractNo", "")
            if cno:
                analysis = analyze_contract(cno)
                if analysis.get("found"):
                    contracts.append(analysis)

    # 也查 00E
    all_00e = supply_cli("search", "00E")
    if isinstance(all_00e, dict) and all_00e.get("matches"):
        for m in all_00e["matches"]:
            cno = m.get("contractNo", "")
            if cno and not any(c["contract"] == cno for c in contracts):
                analysis = analyze_contract(cno)
                if analysis.get("found"):
                    contracts.append(analysis)

    # 按联系人分组 (只分组需要行动的批次)
    groups = {}
    for c in contracts:
        for b in c["batches"]:
            if b["contact_role"]:
                key = f"{b['contact_role']}"
                if key not in groups:
                    groups[key] = {"role": b["contact_role"], "contracts": {}}
                cno = c["contract"]
                if cno not in groups[key]["contracts"]:
                    groups[key]["contracts"][cno] = {
                        "contract": cno,
                        "project": c["project"],
                        "customer": c["customer"],
                        "batches": [],
                    }
                groups[key]["contracts"][cno]["batches"].append(b)

    # 转成列表
    alert_groups = []
    for key, g in groups.items():
        total_batches = sum(len(c["batches"]) for c in g["contracts"].values())
        alert_groups.append({
            "role": g["role"],
            "total_batches": total_batches,
            "total_contracts": len(g["contracts"]),
            "contracts": list(g["contracts"].values()),
        })

    # 统计
    red = sum(1 for c in contracts if c["temperature"] == "red")
    yellow = sum(1 for c in contracts if c["temperature"] == "yellow")
    green = sum(1 for c in contracts if c["temperature"] == "green")

    return {
        "stats": {"red": red, "yellow": yellow, "green": green, "total": len(contracts)},
        "alert_groups": alert_groups,
        "contracts": contracts,
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

@app.post("/api/fragment")
async def receive_fragment(fragment: Fragment):
    """接收 ClipQ 碎片推送"""
    # TODO: 触发 analyze_contract + 更新仪表盘
    return {"received": True, "contract": fragment.contract}


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

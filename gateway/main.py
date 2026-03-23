"""
Supply Owl — API Gateway
仪表盘后端：supply-cli 查数据 + 代码做判断 + 返回结构化 JSON
"""

import json
import re
import os
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


# ========== Models ==========
class Fragment(BaseModel):
    contract: str
    source: str
    context: Optional[str] = None
    sender: Optional[str] = None


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

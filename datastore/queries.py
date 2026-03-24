"""
统一数据读取层 — gateway / MCP / Agent 都通过这里读数据

职责：
1. 从 SQLite 读原始数据
2. 代码做判断（风险等级、风险、联系人路由）
3. 返回结构化结果

不做：LLM 调用、消息生成、UI 渲染
"""
from datetime import datetime
from typing import Optional

from .db import OwlDB
from .models import ContractBatch, ProgressNote


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _days_diff(d1: str, d2: str) -> int:
    try:
        return abs((datetime.strptime(d2, "%Y-%m-%d") - datetime.strptime(d1, "%Y-%m-%d")).days)
    except (ValueError, TypeError):
        return 0


# ── 批次判断（纯代码，不过模型）──────────────────────

def analyze_batch(b: ContractBatch) -> dict:
    """单个批次的风险判断"""
    today = _today()
    cpd = b.cpd
    rpd = b.rpd or ""
    apd = b.apd
    urgent = b.urgent_flag in ("Y", "1")
    short = b.short_item in ("Y", "1") if b.short_item else False
    related = b.related_contract_no

    # CPD vs RPD 判断
    if not cpd:
        status = "uncommitted"
        risk_label = "未承诺"
        contact_role = "承诺坐席"
        contact_reason = "未承诺 → 承诺坐席"
    elif rpd and cpd > rpd:
        gap = _days_diff(rpd, cpd)
        status = "not_met"
        risk_label = f"不满足(差{gap}天)"
        if (b.batch_no or "").startswith("HWA"):
            contact_role = "大调度"
            contact_reason = "HWA开头 → 直接用1Y0找大调度"
        elif related:
            contact_role = "大调度"
            contact_reason = f"有关联00E → 用{related}找大调度"
        else:
            contact_role = "提拉座席"
            contact_reason = "非HWA+无00E → 提拉座席"
    elif apd:
        status = "delivered"
        risk_label = "已交单"
        contact_role = None
        contact_reason = None
    else:
        status = "met"
        risk_label = "满足"
        contact_role = None
        contact_reason = None

    pull_target = rpd if status == "not_met" else None

    return {
        "batch": b.batch_no,
        "cpd": cpd,
        "rpd": rpd,
        "apd": apd,
        "status": status,
        "risk_label": risk_label,
        "urgent": urgent,
        "short": short,
        "contact_role": contact_role,
        "contact_reason": contact_reason,
        "pull_target": pull_target,
        "dispatcher": b.dispatcher,
        "supply_manager": b.supply_manager,
        "product": b.product_coa,
    }


# ── 合同分析 ──────────────────────────────────────

def analyze_contract(db: OwlDB, contract_no: str) -> dict:
    """合同级分析"""
    batches = db.get_all_batches(contract_no)
    if not batches:
        return {"contract": contract_no, "found": False}

    analyzed = [analyze_batch(b) for b in batches]
    first = batches[0]

    # 合同风险等级
    if any(a["status"] == "not_met" and a["urgent"] for a in analyzed):
        risk_level = "red"
    elif any(a["status"] == "not_met" for a in analyzed):
        risk_level = "yellow"
    elif any(a["status"] == "uncommitted" for a in analyzed):
        risk_level = "yellow"
    else:
        risk_level = "green"

    return {
        "contract": contract_no,
        "found": True,
        "project": first.project_name or "",
        "customer": first.customer or "",
        "risk_level": risk_level,
        "batches": analyzed,
    }


# ── 仪表盘 ────────────────────────────────────────

def build_dashboard(db: OwlDB) -> dict:
    """构建完整仪表盘数据 — 按联系人分组"""
    summary = db.get_contracts_summary()
    contracts = []
    for s in summary:
        analysis = analyze_contract(db, s["contract_no"])
        if analysis.get("found"):
            contracts.append(analysis)

    # 按联系人角色分组（只分组需要行动的批次）
    groups: dict[str, dict] = {}
    for c in contracts:
        for b in c["batches"]:
            role = b["contact_role"]
            if not role:
                continue
            if role not in groups:
                groups[role] = {"role": role, "contracts": {}}
            cno = c["contract"]
            if cno not in groups[role]["contracts"]:
                groups[role]["contracts"][cno] = {
                    "contract": cno,
                    "project": c["project"],
                    "customer": c["customer"],
                    "batches": [],
                }
            groups[role]["contracts"][cno]["batches"].append(b)

    alert_groups = []
    for g in groups.values():
        total_batches = sum(len(c["batches"]) for c in g["contracts"].values())
        alert_groups.append({
            "role": g["role"],
            "total_batches": total_batches,
            "total_contracts": len(g["contracts"]),
            "contracts": list(g["contracts"].values()),
        })

    red = sum(1 for c in contracts if c["risk_level"] == "red")
    yellow = sum(1 for c in contracts if c["risk_level"] == "yellow")
    green = sum(1 for c in contracts if c["risk_level"] == "green")

    return {
        "total_contracts": len(contracts),
        "red": red,
        "yellow": yellow,
        "green": green,
        "alert_groups": alert_groups,
        "contracts": contracts,
    }


# ── 按联系人聚合（给 Agent/MCP 用）────────────────

def aggregate_by_contact(db: OwlDB) -> dict:
    """按联系人聚合需要提拉的合同"""
    dashboard = build_dashboard(db)
    result = {}
    for group in dashboard["alert_groups"]:
        role = group["role"]
        items = []
        for c in group["contracts"]:
            for b in c["batches"]:
                items.append({
                    "contract_no": c["contract"],
                    "customer": c["customer"],
                    "project": c["project"],
                    "batch": b["batch"],
                    "reason": b["risk_label"],
                    "contact_reason": b["contact_reason"],
                    "urgent": b["urgent"],
                    "rpd": b["rpd"],
                    "cpd": b["cpd"],
                })
        result[role] = items
    return result


# ── 进展记录 ──────────────────────────────────────

def add_progress(db: OwlDB, contract_no: str, contact: str,
                 content: str, parsed_summary: str = "",
                 batch_no: Optional[str] = None) -> int:
    note = ProgressNote(
        contract_no=contract_no,
        batch_no=batch_no,
        contact=contact,
        content=content,
        parsed_summary=parsed_summary,
    )
    return db.add_progress_note(note)


def get_full_picture(db: OwlDB, contract_no: Optional[str] = None) -> dict:
    """全貌 = 合同状态 + 最近进展"""
    if contract_no:
        analysis = analyze_contract(db, contract_no)
        notes = db.get_progress_notes(contract_no, limit=20)
    else:
        analysis = build_dashboard(db)
        notes = db.get_progress_notes(limit=50)

    return {
        "state": analysis,
        "recent_notes": [
            {
                "contract_no": n.contract_no,
                "contact": n.contact,
                "content": n.content,
                "parsed_summary": n.parsed_summary,
                "created_at": n.created_at,
            }
            for n in notes
        ],
    }

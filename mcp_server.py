"""
Supply Owl MCP Server — nanobot 通过这个接入 datastore
stdio 模式，nanobot 启动时自动拉起

工具：查合同、查详情、聚合联系人、录入碎片、生成摘要
"""
import os
import sys
import json
from pathlib import Path

# 绕过系统代理
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datastore import OwlDB
from datastore.queries import (
    analyze_contract, build_dashboard, aggregate_by_contact,
    add_progress, get_full_picture,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("请安装 mcp: pip install mcp", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("supply-owl")

# 数据库
OWL_DB_PATH = os.environ.get("OWL_DB_PATH", str(Path(__file__).parent / "owl.db"))
db = OwlDB(OWL_DB_PATH)


@mcp.tool()
def query_dashboard() -> str:
    """查看仪表盘概览：所有合同的风险分布和需要行动的告警组"""
    data = build_dashboard(db)
    return json.dumps({
        "总合同数": data["total_contracts"],
        "红色(高风险)": data["red"],
        "黄色(有风险)": data["yellow"],
        "绿色(正常)": data["green"],
        "告警组": [
            {
                "角色": g["role"],
                "合同数": g["total_contracts"],
                "批次数": g["total_batches"],
            }
            for g in data["alert_groups"]
        ],
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def query_contract(contract_no: str) -> str:
    """查询单个合同的详情，包括每个批次的风险状态、CPD/RPD、联系人

    Args:
        contract_no: 合同号，如 1Y01052508474L
    """
    data = analyze_contract(db, contract_no.upper())
    if not data.get("found"):
        return json.dumps({"error": f"未找到合同 {contract_no}"}, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def query_contacts() -> str:
    """按联系人聚合需要提拉的合同，返回"该找谁、带哪些合同去问"""
    groups = aggregate_by_contact(db)
    return json.dumps(groups, ensure_ascii=False, indent=2)


@mcp.tool()
def query_full_picture(contract_no: str = "") -> str:
    """查看全貌：合同状态 + 最近的进展记录

    Args:
        contract_no: 合同号（可选，不填则返回全局全貌）
    """
    cno = contract_no.upper() if contract_no else None
    data = get_full_picture(db, cno)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def record_fragment(contract_no: str, contact: str, content: str) -> str:
    """录入碎片信息——某人回复了关于某个合同的消息

    Args:
        contract_no: 合同号
        contact: 谁回复的，如"大调度 张工"
        content: 回复原文
    """
    note_id = add_progress(db, contract_no.upper(), contact, content)
    return json.dumps({
        "status": "已录入",
        "id": note_id,
        "contract_no": contract_no.upper(),
        "contact": contact,
    }, ensure_ascii=False)


@mcp.tool()
def query_progress(contract_no: str = "") -> str:
    """查看进展记录

    Args:
        contract_no: 合同号（可选，不填则返回最近所有进展）
    """
    cno = contract_no.upper() if contract_no else None
    notes = db.get_progress_notes(cno, limit=20)
    result = [
        {
            "合同号": n.contract_no,
            "联系人": n.contact,
            "内容": n.content,
            "摘要": n.parsed_summary,
            "时间": n.created_at,
        }
        for n in notes
    ]
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")

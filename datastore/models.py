"""
数据模型 — 对齐 supply-cli types.ts
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContractBatch:
    """合同批次（对齐 ContractBatchEntry）"""
    key: str                          # contractNo + batchNo 组合键
    contract_no: str
    batch_no: str
    project_name: Optional[str] = None
    customer: Optional[str] = None
    iso: Optional[str] = None
    product_coa: Optional[str] = None
    dispatcher: Optional[str] = None       # 大调度
    order_confirm_date: Optional[str] = None
    rpd: Optional[str] = None              # 需求计划日期
    cpd: Optional[str] = None              # 承诺交付日期
    epd_a: Optional[str] = None            # EPD-A
    apd: Optional[str] = None              # 实际交单日期
    supply_manager: Optional[str] = None   # 供应经理
    fc_handler: Optional[str] = None
    coordinator: Optional[str] = None      # 资源统筹
    representative: Optional[str] = None
    complete_no: Optional[str] = None
    demand_status: Optional[str] = None
    promise_status: Optional[int] = None
    promise_status_str: Optional[str] = None
    short_item: Optional[str] = None       # 欠料标识
    product_coa_number: Optional[str] = None
    physical_flag: Optional[str] = None
    sub1_amount: Optional[str] = None
    urgent_flag: Optional[str] = None      # 急单标识
    related_contract_no: Optional[str] = None
    related_batch_no: Optional[str] = None
    related_batch_epd_a: Optional[str] = None
    last_updated: int = 0                  # timestamp ms


@dataclass
class CollabCase:
    """协同工单（对齐 CollabCaseEntry）"""
    case_id: str
    type: str
    contract_no: str
    batch_no: Optional[str] = None
    source_id: str = ""
    status: str = ""
    handler: Optional[str] = None
    title: str = ""
    created_at: int = 0
    updated_at: int = 0
    closed_at: Optional[int] = None
    first_seen_at: int = 0
    last_seen_at: Optional[int] = None


@dataclass
class ContractMeta:
    """合同元数据（对齐 ContractMeta）"""
    contract: str
    project_name: Optional[str] = None
    iso: Optional[str] = None
    last_seen: int = 0
    user_viewed_ts: Optional[int] = None


@dataclass
class ProgressNote:
    """进展记录 — supply-owl 自有，不来自 supply-cli"""
    id: Optional[int] = None
    contract_no: str = ""
    batch_no: Optional[str] = None
    contact: str = ""              # 谁回复的（如"大调度 张工"）
    content: str = ""              # 原文
    parsed_summary: str = ""       # LLM 解析后的结构化摘要
    created_at: int = 0            # timestamp ms

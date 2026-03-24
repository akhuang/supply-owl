"""queries 读取层测试"""
import json
import pytest

from datastore.db import OwlDB
from datastore.queries import (
    analyze_batch, analyze_contract, build_dashboard,
    aggregate_by_contact, add_progress, get_full_picture,
)
from datastore.models import ContractBatch


@pytest.fixture
def db(tmp_path):
    db = OwlDB(str(tmp_path / "test.db"))
    # 导入测试快照
    snapshot = {
        "version": 1,
        "exportedAt": "2026-03-24T10:00:00Z",
        "contractBatches": [
            {
                "key": "1Y010525_B001", "contractNo": "1Y01052508474L", "batchNo": "B001",
                "projectName": "江苏移动城域网扩容", "customer": "中国移动",
                "productCoa": "OptiX OSN 9800", "dispatcher": "张工",
                "rpd": "2026-03-29", "cpd": None,
                "supplyManager": "李经理", "shortItem": "Y", "urgentFlag": "1",
                "lastUpdated": 1711267200000,
            },
            {
                "key": "1Y028937_B001", "contractNo": "1Y02893760876C", "batchNo": "B001",
                "projectName": "德国5G回传", "customer": "Vodafone",
                "productCoa": "OptiX OSN 1800", "dispatcher": "张工",
                "rpd": "2026-04-03", "cpd": "2026-04-11",
                "supplyManager": "王经理", "shortItem": "Y",
                "lastUpdated": 1711267200000,
            },
            {
                "key": "1Y045678_B001", "contractNo": "1Y04567891234D", "batchNo": "HWA001",
                "projectName": "西班牙光网改造", "customer": "Telefonica",
                "productCoa": "NetEngine 8000", "dispatcher": "王工",
                "rpd": "2026-03-21", "cpd": "2026-03-28",
                "supplyManager": "王经理",
                "lastUpdated": 1711267200000,
            },
            {
                "key": "1Y056789_B001", "contractNo": "1Y05678901234E", "batchNo": "B001",
                "projectName": "DT核心路由器", "customer": "Deutsche Telekom",
                "productCoa": "NetEngine 8000", "dispatcher": "王工",
                "rpd": "2026-04-08", "cpd": "2026-04-05",
                "supplyManager": "赵经理",
                "lastUpdated": 1711267200000,
            },
        ],
        "collabCases": [],
        "contractMeta": [],
        "contractQueryEvents": [],
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot))
    db.import_snapshot(str(path))
    yield db
    db.close()


# ── 批次判断 ──────────────────────────────────────

def test_analyze_batch_uncommitted(db):
    batches = db.get_all_batches("1Y01052508474L")
    result = analyze_batch(batches[0])
    assert result["status"] == "uncommitted"
    assert result["contact_role"] == "承诺坐席"
    assert result["urgent"] is True


def test_analyze_batch_not_met(db):
    batches = db.get_all_batches("1Y02893760876C")
    result = analyze_batch(batches[0])
    assert result["status"] == "not_met"
    assert "不满足" in result["risk_label"]


def test_analyze_batch_not_met_hwa(db):
    batches = db.get_all_batches("1Y04567891234D")
    result = analyze_batch(batches[0])
    assert result["status"] == "not_met"
    assert result["contact_role"] == "大调度"
    assert "HWA" in result["contact_reason"]


def test_analyze_batch_met(db):
    batches = db.get_all_batches("1Y05678901234E")
    result = analyze_batch(batches[0])
    assert result["status"] == "met"
    assert result["contact_role"] is None


# ── 合同分析 ──────────────────────────────────────

def test_analyze_contract(db):
    result = analyze_contract(db, "1Y01052508474L")
    assert result["found"] is True
    assert result["risk_level"] in ("yellow", "red")  # uncommitted + urgent
    assert result["customer"] == "中国移动"


def test_analyze_contract_not_found(db):
    result = analyze_contract(db, "NONEXISTENT")
    assert result["found"] is False


# ── 仪表盘 ────────────────────────────────────────

def test_build_dashboard(db):
    dashboard = build_dashboard(db)
    assert dashboard["total_contracts"] == 4
    assert dashboard["red"] + dashboard["yellow"] + dashboard["green"] == 4
    assert len(dashboard["alert_groups"]) > 0


def test_dashboard_groups_have_contracts(db):
    dashboard = build_dashboard(db)
    for group in dashboard["alert_groups"]:
        assert group["total_contracts"] > 0
        assert group["total_batches"] > 0
        for c in group["contracts"]:
            assert "contract" in c
            assert len(c["batches"]) > 0


# ── 按联系人聚合 ──────────────────────────────────

def test_aggregate_by_contact(db):
    groups = aggregate_by_contact(db)
    assert len(groups) > 0
    # 至少有承诺坐席（因为有未承诺的合同）
    assert "承诺坐席" in groups
    for role, items in groups.items():
        assert len(items) > 0
        for item in items:
            assert "contract_no" in item
            assert "reason" in item


# ── 进展记录 + 全貌 ───────────────────────────────

def test_add_progress_and_full_picture(db):
    add_progress(db, "1Y01052508474L", "大调度 张工", "光模块下周三到20个", "ETA 周三 x20")

    picture = get_full_picture(db, "1Y01052508474L")
    assert picture["state"]["found"] is True
    assert len(picture["recent_notes"]) == 1
    assert picture["recent_notes"][0]["contact"] == "大调度 张工"


def test_full_picture_global(db):
    add_progress(db, "1Y01052508474L", "张工", "msg1")
    add_progress(db, "1Y02893760876C", "钱工", "msg2")

    picture = get_full_picture(db)
    assert picture["state"]["total_contracts"] == 4
    assert len(picture["recent_notes"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

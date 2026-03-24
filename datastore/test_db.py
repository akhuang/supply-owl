"""OwlDB 测试"""
import json
import os
import tempfile
import pytest

from datastore.db import OwlDB
from datastore.models import ProgressNote


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = OwlDB(db_path)
    yield db
    db.close()


@pytest.fixture
def snapshot_file(tmp_path):
    """模拟 supply-cli 的 JSON 快照"""
    data = {
        "version": 1,
        "exportedAt": "2026-03-24T10:00:00Z",
        "contractBatches": [
            {
                "key": "1Y010525_B001",
                "contractNo": "1Y01052508474L",
                "batchNo": "B001",
                "projectName": "江苏移动城域网扩容",
                "customer": "中国移动",
                "iso": "CN",
                "productCoa": "OptiX OSN 9800",
                "dispatcher": "张工",
                "rpd": "2026-03-29",
                "cpd": None,
                "epdA": None,
                "apd": None,
                "supplyManager": "李经理",
                "shortItem": "Y",
                "urgentFlag": "1",
                "lastUpdated": 1711267200000,
            },
            {
                "key": "1Y010525_B002",
                "contractNo": "1Y01052508474L",
                "batchNo": "B002",
                "projectName": "江苏移动城域网扩容",
                "customer": "中国移动",
                "productCoa": "OptiX OSN 9800",
                "dispatcher": "张工",
                "rpd": "2026-04-05",
                "cpd": "2026-04-10",
                "supplyManager": "李经理",
                "lastUpdated": 1711267200000,
            },
            {
                "key": "1Y028937_B001",
                "contractNo": "1Y02893760876C",
                "batchNo": "B001",
                "projectName": "德国5G回传",
                "customer": "Vodafone",
                "iso": "DE",
                "productCoa": "OptiX OSN 1800",
                "dispatcher": "张工",
                "rpd": "2026-04-03",
                "cpd": "2026-04-11",
                "supplyManager": "王经理",
                "shortItem": "Y",
                "lastUpdated": 1711267200000,
            },
            {
                "key": "1Y045678_B001",
                "contractNo": "1Y04567891234D",
                "batchNo": "B001",
                "projectName": "西班牙光网改造",
                "customer": "Telefonica",
                "productCoa": "NetEngine 8000",
                "dispatcher": "王工",
                "rpd": "2026-03-21",
                "cpd": "2026-03-21",
                "supplyManager": "王经理",
                "shortItem": "Y",
                "lastUpdated": 1711267200000,
            },
        ],
        "collabCases": [
            {
                "caseId": "CASE001",
                "type": "expedite",
                "contractNo": "1Y01052508474L",
                "batchNo": "B001",
                "sourceId": "SRC001",
                "status": "open",
                "handler": "张工",
                "title": "100G光模块缺料提拉",
                "createdAt": 1711267200000,
                "updatedAt": 1711267200000,
                "firstSeenAt": 1711267200000,
            },
        ],
        "contractMeta": [
            {
                "contract": "1Y01052508474L",
                "projectName": "江苏移动城域网扩容",
                "iso": "CN",
                "lastSeen": 1711267200000,
            },
            {
                "contract": "1Y02893760876C",
                "projectName": "德国5G回传",
                "iso": "DE",
                "lastSeen": 1711267200000,
            },
        ],
        "contractQueryEvents": [],
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(data))
    return str(path)


# ── 建表测试 ──────────────────────────────────────

def test_schema_created(db):
    tables = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = [t["name"] for t in tables]
    assert "contract_batch" in names
    assert "collab_case" in names
    assert "contract_meta" in names
    assert "progress_note" in names
    assert "sync_meta" in names


# ── 导入测试 ──────────────────────────────────────

def test_import_snapshot(db, snapshot_file):
    stats = db.import_snapshot(snapshot_file)
    assert stats["batches"] == 4
    assert stats["cases"] == 1
    assert stats["metas"] == 2


def test_import_idempotent(db, snapshot_file):
    """重复导入不会重复插入"""
    db.import_snapshot(snapshot_file)
    db.import_snapshot(snapshot_file)
    batches = db.get_all_batches()
    assert len(batches) == 4


def test_import_bad_version(db, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 99}))
    with pytest.raises(ValueError, match="不支持的快照版本"):
        db.import_snapshot(str(path))


# ── 查询测试 ──────────────────────────────────────

def test_get_all_batches(db, snapshot_file):
    db.import_snapshot(snapshot_file)
    batches = db.get_all_batches()
    assert len(batches) == 4
    assert batches[0].contract_no == "1Y01052508474L"


def test_get_batches_by_contract(db, snapshot_file):
    db.import_snapshot(snapshot_file)
    batches = db.get_all_batches("1Y01052508474L")
    assert len(batches) == 2
    assert all(b.contract_no == "1Y01052508474L" for b in batches)


def test_get_batches_by_dispatcher(db, snapshot_file):
    db.import_snapshot(snapshot_file)
    batches = db.get_batches_by_dispatcher("张工")
    assert len(batches) == 3  # B001, B002 of contract1 + B001 of contract2


def test_get_batches_by_supply_manager(db, snapshot_file):
    db.import_snapshot(snapshot_file)
    batches = db.get_batches_by_supply_manager("王经理")
    assert len(batches) == 2


def test_get_contracts_summary(db, snapshot_file):
    db.import_snapshot(snapshot_file)
    summary = db.get_contracts_summary()
    assert len(summary) == 3  # 3 个不同的合同

    # 找中国移动的合同
    cm = next(s for s in summary if s["contract_no"] == "1Y01052508474L")
    assert cm["batch_count"] == 2
    assert cm["customer"] == "中国移动"
    assert cm["uncommitted_count"] == 1  # B001 没有 CPD
    assert cm["shortage_count"] == 1     # B001 有 shortItem
    assert cm["urgent_count"] == 1       # B001 是急单


def test_get_collab_cases(db, snapshot_file):
    db.import_snapshot(snapshot_file)
    cases = db.get_collab_cases()
    assert len(cases) == 1
    assert cases[0].case_id == "CASE001"
    assert cases[0].status == "open"


def test_get_collab_cases_by_contract(db, snapshot_file):
    db.import_snapshot(snapshot_file)
    cases = db.get_collab_cases("1Y01052508474L")
    assert len(cases) == 1
    cases_empty = db.get_collab_cases("1Y04567891234D")
    assert len(cases_empty) == 0


# ── 进展记录测试 ──────────────────────────────────

def test_add_and_get_progress_note(db):
    note = ProgressNote(
        contract_no="1Y01052508474L",
        batch_no="B001",
        contact="大调度 张工",
        content="光模块下周三能到20个",
        parsed_summary="100G光模块 ETA 周三 数量20",
    )
    note_id = db.add_progress_note(note)
    assert note_id > 0

    notes = db.get_progress_notes("1Y01052508474L")
    assert len(notes) == 1
    assert notes[0].contact == "大调度 张工"
    assert notes[0].content == "光模块下周三能到20个"


def test_get_progress_notes_all(db):
    db.add_progress_note(ProgressNote(
        contract_no="1Y010525", contact="张工", content="msg1",
    ))
    db.add_progress_note(ProgressNote(
        contract_no="1Y028937", contact="钱工", content="msg2",
    ))
    notes = db.get_progress_notes()
    assert len(notes) == 2


# ── 同步信息测试 ──────────────────────────────────

def test_sync_info(db, snapshot_file):
    db.import_snapshot(snapshot_file)
    info = db.get_sync_info()
    assert "last_snapshot_import" in info
    assert snapshot_file in info["last_snapshot_import"]["value"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

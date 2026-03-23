"""消息 API 测试"""
import os
import pytest
from fastapi.testclient import TestClient

# 用临时数据库，不污染正式数据
os.environ["TESTING"] = "1"

from main import app, DB_PATH, _init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清空消息表"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM messages")
    conn.commit()
    conn.close()
    yield


class TestDraft:
    def test_draft_承诺坐席(self):
        r = client.post("/api/draft", json={
            "role": "承诺坐席",
            "contracts": [{"contract": "1Y01052508474L"}],
            "batches": [
                {"contract": "1Y01052508474L", "batch": "HWC0044Q", "rpd": "2026-03-25", "cpd": None},
                {"contract": "1Y01052508474L", "batch": "HWC0098R", "rpd": "2026-03-28", "cpd": None},
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert "请协助确认" in data["draft"]
        assert "HWC0044Q" in data["draft"]
        assert "HWC0098R" in data["draft"]

    def test_draft_大调度(self):
        r = client.post("/api/draft", json={
            "role": "大调度",
            "contracts": [{"contract": "1Y02893760876C"}],
            "batches": [
                {"contract": "1Y02893760876C", "batch": "HWA0012Q", "rpd": "2026-03-30", "cpd": "2026-04-05"},
            ]
        })
        assert r.status_code == 200
        assert "提拉" in r.json()["draft"]


class TestMessages:
    def test_send_and_list(self):
        # 发送
        r = client.post("/api/messages", json={
            "role": "承诺坐席",
            "action": "催承诺",
            "contracts": ["1Y01052508474L"],
            "batches": [{"batch": "HWC0044Q", "rpd": "2026-03-25"}],
            "draft_text": "请确认承诺日期"
        })
        assert r.status_code == 200
        msg_id = r.json()["id"]
        assert r.json()["status"] == "waiting"

        # 列出 waiting
        r = client.get("/api/messages?status=waiting")
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) == 1
        assert msgs[0]["id"] == msg_id
        assert msgs[0]["role"] == "承诺坐席"
        assert msgs[0]["contracts"] == ["1Y01052508474L"]

    def test_reply(self):
        # 先发送
        r = client.post("/api/messages", json={
            "role": "大调度",
            "action": "批量提拉",
            "contracts": ["1Y02893760876C"],
            "batches": [{"batch": "HWA0012Q"}],
            "draft_text": "请提拉"
        })
        msg_id = r.json()["id"]

        # 收到回复
        r = client.put(f"/api/messages/{msg_id}/reply", json={
            "reply_text": "已安排提拉，04-02到货"
        })
        assert r.status_code == 200
        assert r.json()["status"] == "replied"

        # waiting 应该为空
        r = client.get("/api/messages?status=waiting")
        assert len(r.json()) == 0

        # replied 应该有 1 条
        r = client.get("/api/messages?status=replied")
        msgs = r.json()
        assert len(msgs) == 1
        assert msgs[0]["reply_text"] == "已安排提拉，04-02到货"

    def test_update_status_to_processed(self):
        r = client.post("/api/messages", json={
            "role": "承诺坐席",
            "action": "催承诺",
            "contracts": ["1Y01052508474L"],
            "batches": [{"batch": "HWC0044Q"}],
            "draft_text": "请确认"
        })
        msg_id = r.json()["id"]

        # 先回复
        client.put(f"/api/messages/{msg_id}/reply", json={"reply_text": "OK"})

        # 标记已处理
        r = client.put(f"/api/messages/{msg_id}", json={"status": "processed"})
        assert r.status_code == 200
        assert r.json()["status"] == "processed"

        # 不再出现在 replied 列表
        r = client.get("/api/messages?status=replied")
        assert len(r.json()) == 0

    def test_list_all(self):
        # 发两条
        client.post("/api/messages", json={
            "role": "承诺坐席", "action": "催承诺",
            "contracts": ["A"], "batches": [], "draft_text": "x"
        })
        client.post("/api/messages", json={
            "role": "大调度", "action": "提拉",
            "contracts": ["B"], "batches": [], "draft_text": "y"
        })
        r = client.get("/api/messages")
        assert len(r.json()) == 2


class TestDashboard:
    def test_dashboard_loads(self):
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "stats" in data
        assert "alert_groups" in data

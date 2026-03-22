"""
Supply Owl — API Gateway
FastAPI 薄层，桥接 Web UI 和 Hermes Agent。
写入经 Hermes（唯一写入者），读取可直读 SQLite。
"""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json

app = FastAPI(title="Supply Owl Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Models ==========

class Fragment(BaseModel):
    """ClipQ / supply-chrome 推送的碎片"""
    contract: str
    source: str  # clipboard | outlook | welink | chrome-intercept
    context: Optional[str] = None
    sender: Optional[str] = None
    timestamp: Optional[int] = None


# ========== Routes ==========

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "supply-owl"}


@app.post("/api/fragment")
async def receive_fragment(fragment: Fragment):
    """接收碎片推送（ClipQ / supply-chrome）"""
    # TODO: 转发给 Hermes Agent 处理
    return {"received": True, "contract": fragment.contract}


@app.get("/api/contracts")
def list_contracts():
    """合同活状态列表（直读 SQLite）"""
    # TODO: 读取 SQLite
    return {"contracts": []}


@app.get("/api/contracts/{contract_id}")
def get_contract(contract_id: str):
    """单合同详情 + 时间线（直读 SQLite）"""
    # TODO: 读取 SQLite
    return {"contract_id": contract_id, "batches": []}


@app.get("/api/alerts")
def list_alerts():
    """预警列表，按联系人分组（直读 SQLite）"""
    # TODO: 读取 SQLite + 按路由规则分组
    return {"groups": []}


@app.get("/api/suggestions")
def list_suggestions():
    """待办建议（从 alerts 推导）"""
    # TODO
    return {"suggestions": []}


@app.get("/api/axioms")
def list_axioms():
    """决策原则列表"""
    # TODO: 读取 MEMORY.md
    return {"axioms": []}


@app.websocket("/ws/copilot")
async def copilot(websocket: WebSocket):
    """Copilot 命令入口 — 流式响应"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # TODO: 转发给 Hermes Agent，流式返回
            await websocket.send_text(json.dumps({
                "type": "response",
                "text": f"收到: {data}"
            }))
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8321)

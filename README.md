# 🦉 Supply Owl

供应链订单履行助手 — 你的夜行分身。

> 不是替你接管复杂工作，是替你承接复杂工作的连续性。

## 它做什么

- **盯** — 持续跟踪每个合同的活状态，不掉线
- **串** — 把零散碎片（WeLink消息、邮件、剪贴板）归位到对应合同
- **提醒** — 发现异常即推送，按"该找谁"分组，批量催办
- **记** — 沉淀你的判断原则（Axioms），越用越懂你

你继续做判断、取舍、协调、拍板。Owl 帮你托住上下文不断线。

## 技术栈

- **引擎**: Hermes Agent (Python)
- **模型**: Ollama 本地 7B + 内部 Qwen3-32B API
- **前端**: Next.js + shadcn/ui
- **数据**: SQLite (合同活状态)
- **集成**: ClipQ (碎片捕获) + supply-cli (11个API) + supply-chrome (浏览器拦截)

## 架构

```
ClipQ / supply-chrome → 碎片推送
                              ↓
                    Hermes Agent (引擎)
                    ├── Brain (双模型路由)
                    ├── Skills (supply-cli 封装)
                    ├── Memory (Axioms + 合同活状态)
                    └── Heartbeat (定时巡检)
                              ↓
                    FastAPI Gateway
                              ↓
                    Web UI (仪表盘)
```

## 状态

Phase 1: 搭建中

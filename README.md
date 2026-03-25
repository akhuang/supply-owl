# 🦉 Supply Owl

供应链订单履行助手 — 你的夜行分身。

> 不是替你接管复杂工作，是替你承接复杂工作的连续性。

## 快速开始

```bash
# 1. Ollama
ollama pull qwen2.5:14b && ollama serve

# 2. Hermes 配置（首次）
cat > ~/.hermes/config.yaml << 'EOF'
model:
  default: "qwen2.5:14b"
  base_url: "http://localhost:11434/v1"
EOF

# 3. 数据初始化（首次）
cd /path/to/supply-owl
python3 -c "
from datastore import OwlDB; from pathlib import Path
db = OwlDB('owl.db')
db.conn.executescript(Path('datastore/seed.sql').read_text())
db.conn.executescript(Path('datastore/seed_extra.sql').read_text())
db.conn.commit(); db.close(); print('20 contracts loaded')
"
```

## 两种使用方式

### Web 仪表盘

```bash
NO_PROXY=localhost,127.0.0.1 python3 -m uvicorn gateway.main:app --port 8000
```

打开 http://localhost:8000

- 仪表盘：按联系人分组的告警面板，批次状态一目了然
- 底部输入框：跟 Owl 对话（查合同、问建议）

### TUI 终端

```bash
cd hermes

# 交互模式
NO_PROXY=localhost,127.0.0.1 python cli.py

# 单次查询
NO_PROXY=localhost,127.0.0.1 python cli.py -q "1Y01052508474L 什么情况"

# 恢复上次会话
NO_PROXY=localhost,127.0.0.1 python cli.py --resume <session_id>
```

TUI 功能更完整：工具调用可视化、会话恢复、技能系统、`/help` 看所有命令。

## 项目结构

```
supply-owl/
├── gateway/                # Web 后端
│   ├── main.py             # FastAPI（仪表盘数据 + AI chat）
│   └── static/index.html   # 仪表盘前端
├── datastore/              # 数据层（25 tests ✅）
│   ├── db.py               # SQLite 存储
│   ├── queries.py          # 统一读取层（代码做判断）
│   ├── models.py           # 数据模型（对齐 supply-cli types）
│   └── schema.sql          # 5 张表
├── ai_engine.py            # Hermes AIAgent 最薄封装
├── mcp_server.py           # MCP 工具（供 Agent 查数据）
├── agent/                  # Owl 人设与记忆
│   ├── SOUL.md             # 人设（像同事不像机器人）
│   ├── MEMORY.md           # 业务决策规则
│   └── USER.md             # 用户画像
├── hermes/                 # Hermes Agent 框架
└── owl.db                  # SQLite 数据库
```

## 设计原则

```
代码做判断 → 风险等级、联系人路由、批次分析（queries.py）
模型说人话 → 碎片解析、消息拟稿、全貌摘要（ai_engine.py）
仪表盘不是聊天 → 主界面是工作台，AI 嵌在操作流程里
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_MODEL` | `qwen2.5:14b` | Ollama 模型名 |
| `OWL_DB_PATH` | `./owl.db` | SQLite 数据库路径 |
| `NO_PROXY` | — | 必须设 `localhost,127.0.0.1` |

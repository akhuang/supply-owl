# 🦉 Supply Owl

供应链订单履行助手 — 你的夜行分身。

> 不是替你接管复杂工作，是替你承接复杂工作的连续性。

## 快速开始

```bash
# 1. Clone
git clone https://github.com/akhuang/supply-owl.git
cd supply-owl

# 2. Hermes Agent（不在 git 里，需要单独 clone）
git clone --depth 1 https://github.com/NousResearch/hermes-agent.git hermes

# 3. Python 依赖
pip install -e hermes
pip install fastapi uvicorn python-dotenv

# 4. Ollama
ollama pull qwen3:32b
ollama serve

# 5. 配置 .env（改模型/API 地址在这里）
# 默认已配好 Ollama 本地，内部环境改 LLM_BASE_URL 和 LLM_API_KEY

# 6. 数据初始化（首次）
python3 -c "
from datastore import OwlDB; from pathlib import Path
db = OwlDB('owl.db')
db.conn.executescript(Path('datastore/seed.sql').read_text())
db.conn.executescript(Path('datastore/seed_extra.sql').read_text())
db.conn.commit(); db.close(); print('20 contracts loaded')
"

# 7. 启动
./run.sh web     # Web 仪表盘
./run.sh tui     # TUI 终端
./run.sh both    # Web + TUI
```

Windows:

```bat
git clone --depth 1 https://github.com/NousResearch/hermes-agent.git hermes
pip install -e hermes
pip install fastapi uvicorn python-dotenv

run.bat web
run.bat tui
run.bat both
```

## 两种使用方式

### Web 仪表盘

```bash
./run.sh web
```

打开 http://localhost:8000

- 仪表盘：按联系人分组的告警面板，批次状态一目了然
- 底部输入框：跟 Owl 对话（查合同、问建议）

### TUI 终端

```bash
./run.sh tui
```

TUI 功能更完整：工具调用可视化、会话恢复、技能系统、`/help` 看所有命令。`run.sh` / `run.bat` 会自动把根目录 `.env` 同步到项目本地 `./.hermes/.env`，不再依赖 `~/.hermes/.env`。

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
├── hermes/                 # Hermes Agent 框架（git clone，不在仓库里）
└── owl.db                  # SQLite 数据库
```

## 设计原则

```
代码做判断 → 风险等级、联系人路由、批次分析（queries.py）
模型说人话 → 碎片解析、消息拟稿、全貌摘要（ai_engine.py）
仪表盘不是聊天 → 主界面是工作台，AI 嵌在操作流程里
```

## 环境变量（.env）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_MODEL` | `qwen3:32b` | Ollama 模型名 |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI 兼容接口地址 |
| `LLM_API_KEY` | `ollama` | OpenAI 兼容接口密钥 |
| `OWL_DB_PATH` | `./owl.db` | SQLite 数据库路径 |
| `NO_PROXY` | — | 必须设 `localhost,127.0.0.1` |

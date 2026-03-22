---
name: supply-scout
description: 收到合同号碎片后，自动并行查询充实上下文
version: 1.0.0
platforms: [linux, darwin]
metadata:
  category: supply-chain
  requires_toolsets: [terminal]
---

## When to Use

ClipQ 或 supply-chrome 推送了一个合同号碎片时，自动触发。

## Procedure

1. 接收碎片: 合同号 + 来源 + 可选上下文
2. 并行调用:
   - `supply-cli detail <合同号>` → 基础信息
   - `supply-cli fetch <合同号>` → 最新批次数据
   - `supply-cli anomalies <合同号>` → 当前异常
3. 合并结果，计算温度
4. 更新合同活状态到 SQLite
5. 如果温度变化，推送到 Web UI

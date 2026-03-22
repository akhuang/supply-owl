---
name: supply-progress
description: 写进展记录到 supply-crawlee
version: 1.0.0
platforms: [linux, darwin]
metadata:
  category: supply-chain
  requires_toolsets: [terminal]
---

## When to Use

用户要写进展、更新合同状态时使用。

## Procedure

1. 确认合同号和批次号
2. 生成进展内容（可用模板或 LLM 润色）
3. 调用 supply-crawlee API: POST /api/progress
4. 更新合同活状态时间线

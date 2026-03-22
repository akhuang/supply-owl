---
name: supply-monitor
description: 异常检测和风险评估，扫描合同活状态变化
version: 1.0.0
platforms: [linux, darwin]
metadata:
  category: supply-chain
  requires_toolsets: [terminal]
---

## When to Use

Heartbeat 定时巡检时使用，或用户问"有什么异常"时使用。

## Procedure

1. 使用 `supply-cli anomalies` 获取所有异常
2. 使用 `supply-cli risk` 获取风险评估
3. 对比上次状态，识别变化（新增/升级/降级/消失）
4. 按温度规则（Axioms）计算每个批次的温度
5. 按"该找谁"路由规则分组

## Pitfalls

- 未承诺本身不是预警，只有供应经理催了才变成预警
- CPD 满足 RPD 不代表完全没事，一线可能仍要求提拉

---
name: supply-query
description: 查询合同和批次信息，返回结构化数据
version: 1.0.0
platforms: [linux, darwin]
metadata:
  category: supply-chain
  requires_toolsets: [terminal]
---

## When to Use

当用户询问某个合同的详情、批次状态、CPD/RPD 等信息时使用。

## Procedure

1. 使用 `supply-cli detail <合同号>` 获取合同详情
2. 如果需要最新数据，先 `supply-cli fetch <合同号>` 刷新
3. 解析 JSON 输出，提取关键字段
4. 按批次分组，标注 CPD vs RPD 状态（未承诺/不满足/满足）

## Pitfalls

- supply-cli 的 session 可能过期，如果返回认证错误，先 `supply-cli refresh`
- 一次不要 fetch 超过 10 个合同，否则 W3 系统会限流
- 合同号格式: 1Y0 或 00E 开头，14 位
- 批次号格式: HW 开头，8 位

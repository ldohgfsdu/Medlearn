# Ingestion Boundary：Parser Heading Stack vs LLM Judgment

> **状态**：已裁决  
> **生效范围**：`evidence_extractor.py` heading stack → 下游 synthesis / knowledge node 生成  
> **关联规则**：ADR-006（教材自持 knowledge aspects）、Phase 1 Source Loop 四条铁律  
> **验证锚点**：第四章 支气管哮喘 p.62–70，`肺功能检查` 及其 4 个子类

## 规则

### R1：Parser heading 栈是结构真相的唯一来源

`evidence_extractor.py` 中 `current_heading` 栈由 PDF 排版信号驱动——字体大小、
heading 前缀（`【】`/`（一）`）、已知 aspect 标签三者共同判定。此栈是下游一切
结构语义的 ground truth，**不得被 LLM 覆盖、纠正或"补全"**。

- 实现位置：`extract_section_evidence()` 中 `_block_is_heading_flag()` +
  `_split_heading_body()` → `current_heading` 赋值。
- 输出载体：每个 `EvidenceArtifact.source_heading`。
- 反例：修复前，`（三）肺功能检查` 因 `<10` 字被丢弃，导致 p.64 后续 85
  条证据全部挂在 `"第四章 支气管哮喘"` 上——丢失了整个检查大类的结构。

### R2：LLM 只做子节点挂载，不做父节点新建

knowledge node / synthesis 阶段（Phase 2+）的 LLM 在生成结构化节点时：

- **允许**：在一个已有 `source_heading` 的 artifact group 下挂载子知识点
  （如 `肺功能检查 → 通气功能检测 → FEV1/FVC＜70% 判断标准`）。
- **禁止**：凭空创建与 parser heading 栈中已有同级标题对等的新检查大类
  （如在没有 parser 信号的情况下，LLM 自行生成 `"影像学检查"` 作为与
  `"实验室和其他检查"` 平级的 top-level 节点）。

判断标准：如果 LLM 想创建一个 heading，先查 `source_heading` 栈中是否已存在
该 heading 或其在 `ASPECT_NORMALIZE` 映射后的 canonical form。

### R3：Parser 的 failure mode 是"漏挂"，不是"错挂"

heading 栈的误判方向是单向的——它可能因为 PDF 排版怪异而**漏识别**一个子标题，
从而把子内容挂在父 heading 下（信息未丢，只是粒度粗了），但**不会凭空捏造**一个
不存在的 heading。

因此，当 LLM 发现"这里明显应该有一个新 heading 但 parser 没给"时，正确的处理是：

- **标记为 `needs_review`**，回到 parser 层修复 heading 检测逻辑。
- **不得**在 synthesis 阶段自行补一个 heading——补丁打在 parser 层，不在 LLM 层。

### R4：`ASPECT_NORMALIZE` 是 aspect 聚合的合法映射，不是 heading 生成器

`_normalize_aspect()` 将 `"实验室和其他辅助检查"` → `"辅助检查"` 是**聚合**操作，
不是**生成**操作。它只在 heading 已被 parser 识别后才触发，不允许 LLM 拿
`ASPECT_NORMALIZE` 的 value 反向推导出"应该有一个 `辅助检查` heading"。

## 验收测试

以下查询必须成立（以第四章 支气管哮喘为例）：

```python
# 1. 肺功能检查下的 4 个子类都正确归属
assert all(a.source_heading == "肺功能检查" for a in artifacts[71:86])

# 2. 胸部X线/CT、特异性变应原、动脉血气 各自独立
assert artifacts[86].source_heading != "肺功能检查"
assert artifacts[87].source_heading == "特异性变应原检测"

# 3. 全章 288 artifacts 中 source_heading 仅 3 条为 "第四章 支气管哮喘"
#   （章节开头的定义段落，尚无子标题）
chapter_level = [a for a in artifacts if a.source_heading == "第四章 支气管哮喘"]
assert len(chapter_level) == 3
```

## 变更历史

| 日期 | 变更 |
|------|------|
| 2026-06-28 | 初稿：基于 heading 栈修复后重跑哮喘节 evidence extract 的 diff 验证结果 |

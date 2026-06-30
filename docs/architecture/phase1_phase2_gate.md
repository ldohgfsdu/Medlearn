# Phase 1 → Phase 2 → Phase 3 闸门规范

**active_object**: `phase1_document_tree_golden_path_validation`（与 `state/active_object.yaml` 一致）  
**状态**: 工程闸门（非产品功能）  
**范围**: 仅定义 Phase 1 完成标准、Phase 2 开工门槛、Phase 3 前置条件。**不改 App、不改数据库、不新增图谱或 AI 功能。**

---

## 定位

MedLearn 的长期目标是**医学知识网络**；当前阶段的工作对象是**知识网络的可信地基**，不是图谱 UI 或概念推理产品。

```text
先让教材可信。
再让概念可识别。
最后让知识可连接。
```

**Phase 1 唯一目标**：在目标章节上跑通 **Document Tree 闭环**。

```text
PDF 教材
  → Source Asset
  → Document Tree
  → Evidence Anchor
  → Document Index
  → App 详情页可读
  → 点击回跳原文
```

---

## 术语与仓库对照

| 本规范用语 | 仓库 / ADR 常用名 |
|------------|-------------------|
| Evidence Anchor | Source Anchor、证据定位（ADR-009）；页图 + bbox 见 `docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md` |
| ContentBlock | 可展示正文块；与 EV1 / Study 展示契约相关 |
| Source Asset | 教材版本、PDF、页图资产、parser `source-artifacts` |
| Document Index | 由 Document Tree 派生的检索与导航层（非事实来源） |
| Canonical Concept | ADR-008 `medical_concept` 方向；Phase 2 再冻结 schema |
| raw_evidence | 低置信度保留原文与定位，禁止 AI 补结构 |

权威产品边界：`docs/PROJECT_CONSTITUTION.md`。执行状态：`state/*.yaml` → `docs/CURRENT_STATE.md`。

---

## Phase 1 完成标准：Document Tree 闭环

### 1. Document Tree 结构验收

必须满足：

```text
1. 教材标题层级正确保留
2. 不把低层级内容拔高
3. children 递归结构稳定
4. source_order 稳定
5. 没有 orphan node
6. evidence_only 不打断主链条
7. OCR 碎片不污染顶层结构
```

**重点案例（结构忠实教材，非“聪明医学分类”）**：

```text
哮喘：
实验室和其他检查
  └── 肺功能检查
      ├── 通气功能检测
      ├── 支气管激发试验
      ├── 支气管舒张试验
      └── PEF

肺结核：
分类标准
  └── 分类轴
      └── 子类型
```

验收原则：

> **教材原来怎么分，App 就怎么呈现。**

### 2. Evidence Anchor 验收

每个可展示内容都必须有证据来源，最低字段集：

```text
textbook_version
page_label
source_heading
raw_text
bbox / page image fallback
artifact_id
```

最低行为：

```text
点击内容 → 能回到教材原文页
```

不追求句子级完美定位；必须达到**页级 / 区域级**回跳。视觉证据链与 P0 签字以 `docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md` 为准（荧光笔叠图、显式 ID join、禁止 LLM 发明 bbox）。

**fallback 例外**：当目标章节暂无 page-image bundle 时，接受等价教材原文上下文（text + page_label）作为回跳 fallback（见 `state/active_object.yaml` acceptance_criteria）；页图 bundle 属可选扩展，非 Phase 1 硬门。本最低行为适用于已具备 page-image 的章节；肺结核 APK 验收见 L160。

**低置信度规则**：

```text
解析不准 → raw_evidence
不能 AI 猜
不能强行结构化
```

### 3. Document Index 验收

Document Index 必须能支持：

```text
标题搜索
正文搜索
章节内跳转
breadcrumb 展示
RAG retrieval chunk 预留
证据回跳
```

**Index 是派生层，不是事实来源。** Index 错了，不得手改 Index；必须回到 DocumentNode / ContentBlock / EvidenceAnchor 修正后**重建**。

### 4. Interaction Layer 验收

App 详情页目标：

```text
像电子教材，而不是碎知识卡片
```

必须支持：

```text
章节目录
层级缩进
折叠 / 展开
锚点跳转
证据按钮
原文回跳
raw_evidence 展示
```

**APK 真机验收标准**（Phase 1 代表章节）：

```text
支气管哮喘完整一节可读
层级清楚
长页面不卡
证据按钮可点
原文页可打开
raw_evidence 不误导用户
```

肺结核分类树递归展示通过，作为结构污染的回归用例。

---

## Phase 1 **不算完成**（任一即禁止进入 Phase 2）

```text
PEF / BDT / BPT 被提到和「实验室和其他检查」同级
肺结核分类树被 OCR 碎片污染
evidence_only 被当成正式整理结论
source_order 不稳定
详情页像知识点列表而不是电子教材
搜索结果无法回跳原文
Document Index 与 Document Tree 内容不一致
低置信度内容被系统硬编结构
```

---

## Phase 2 开工门槛：Concept Layer（Semantic Layer）

Phase 1 在**目标章节**上持续稳定，并通过真机阅读与证据回跳验收后，才允许进入 Phase 2。

Phase 2 的目标**不是**知识图谱 UI，而是：

```text
Document Tree
  → Concept Mention
  → Canonical Concept
  → Alias
  → Review State
```

### Phase 2 可以开始的条件（全部满足）

```text
1. Document Tree schema 冻结
2. EvidenceAnchor schema 冻结
3. DocumentIndex 可稳定重建
4. 支气管哮喘完整节通过 APK 验收
5. 肺结核分类树递归展示通过
6. OCR 碎片污染有自动检测 / QA
7. display contract 有回归测试
8. 每个可展示内容都能定位到 SourceAsset
```

此后才允许抽取候选类型（示例，非一次性全量）：

```text
疾病、症状、体征、检查、指标、药物、机制、病原体、解剖结构、病理过程
```

### Phase 2 初始目标（刻意收窄）

不要一上来建完整知识图谱。先做：

```text
ConceptMention 候选抽取
CanonicalConcept 最小表
aliases 别名表
reviewState 审核状态
evidenceAnchorIds 证据绑定
```

示例：

```text
surfaceForm: FEV1
canonicalConcept: 第一秒用力呼气容积
type: pulmonary_function_index
evidence: 内科学第10版 → 支气管哮喘 → 肺功能检查
reviewState: pending
```

与 ADR-008（概念复用与详情实例隔离）对齐；具体表结构在 Phase 2 开工时单独 ADR / schema 冻结，本闸门文档不展开实现。

---

## Phase 3 开工门槛：Knowledge Graph

Phase 3 才开始做**关系边**：

```text
Concept
  → Relation
  → Evidence
  → Review
```

示例：

```text
支气管舒张试验 → used_for → 判断气道可逆性改变
FeNO           → used_for → 评估哮喘控制水平
ICS            → treats   → 支气管哮喘
```

每条边必须满足：

```text
有 relationType
有 evidenceAnchorIds
有 confidence
有 reviewState
能回跳教材
```

**无证据边不能进入 verified。**

Phase 3 前置：Phase 2 中 ConceptMention 与 CanonicalConcept 的**证据绑定**与**审核状态**在试点章节上稳定，且有可重复的 QA / 回归。

---

## 闸门总则（canonical）

> **只有当 Document Tree、Evidence Anchor、Document Index 在目标章节上持续稳定，并通过真机阅读与证据回跳验收后，才允许进入 Semantic Layer；只有当 ConceptMention 与 CanonicalConcept 的证据绑定和审核状态稳定后，才允许进入 Knowledge Graph。**

更短版本：

```text
先让教材可信。
再让概念可识别。
最后让知识可连接。
```

---

## 相关文档

| 文档 | 用途 |
|------|------|
| `docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md` | Phase 1 视觉证据与回跳铁律 |
| `docs/PDF_PARSER_ARCHITECTURE.md` | 解析、OCR、`source-artifacts` |
| `docs/adr/ADR-009-multimodal-evidence-artifacts.md` | 证据工件与锚点 |
| `docs/adr/ADR-008-concept-reuse-detail-isolation.md` | Phase 2 概念层方向 |
| `docs/PROJECT_CONSTITUTION.md` | 产品身份与层级 |

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-26 | 初版：Phase 1/2/3 闸门与验收清单（`phase1_to_phase2_gate_spec`） |
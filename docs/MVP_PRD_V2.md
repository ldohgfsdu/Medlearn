# MedLearn MVP PRD V2

> Status: Documentation convergence baseline
> Source of product identity: `docs/PROJECT_CONSTITUTION.md`
> Source of current execution state: `docs/CURRENT_STATE.md` and `state/*.yaml`

## 1. Product Identity

MedLearn 是以结构化医学知识为基础的临床思维训练系统。

书是基础。框架是核心。推理是终点。

## 2. User

### Primary Users

- 临床过渡期医学生：从知识记忆进入病例推理训练阶段的学习者。
- 低年资住院医师：希望通过短时、高质量练习巩固常见主诉和临床推理流程的学习者。

### Not Users

MedLearn 不面向：

- 真实患者；
- 临床诊疗决策；
- 医院 credentialing 或正式能力评估；
- 机构管理者或团队管理场景。

## 3. Core Capabilities And Journeys

Knowledge 与 Case Simulator 是平级、完全独立的核心能力，不构成强制漏斗。

### Knowledge Journey

1. 用户通过 Search 或 Catalog 进入结构化医学 Knowledge。
2. 用户阅读教材依据、结构化要点和概念关系。
3. 用户完成理论知识的查找、理解或复习。

### Case Simulator Journey

1. 用户可以不经过 Knowledge，直接从主诉开始病例。
2. 用户完成患者信息收集、查体/检查、诊断与处理决策。
3. 用户获得 Scoring / Feedback。
4. 用户根据反馈修正一个明确的薄弱点。

Case Simulator 的作用是训练 **Knowledge Application**：把学习者已经掌握的理论知识迁移到临床情境。病例反馈可以提供相关 Knowledge 的可选链接，但不得建立前置学习、解锁关系、强制跳转或完成依赖。

MVP 支持两条独立路径，并允许用户自主跨越：

```text
Knowledge：查找 → 理解 → 复习

Case Simulator：临床应用 → 评分反馈 → 修正
```

## 4. Product Layers

```text
L0 Knowledge
   ↓
L1 Understanding
   ↓
L2 Framework
   ↓
L3 Clinical Reasoning
```

### L0 Knowledge

结构化医学知识基础设施，包括教材、目录、搜索和知识详情。

### L1 Understanding

帮助用户理解和复述知识，包括机制解释、概念关系和费曼式表达。

### L2 Framework

帮助用户组织临床问题，包括症状学框架、鉴别诊断方法、VINDICATE 和临床推理模板。

### L3 Clinical Reasoning

通过病例模拟训练证据整合、诊疗决策、评分反馈和针对性复盘。

## 5. Priority Model

MVP V2 使用以下优先级原则：

> Reality defines existence.
>
> Validation defines importance.
>
> Identity defines priority.

代码存在不自动意味着该能力进入 P0。能力优先级必须根据产品身份、用户验证和当前 MVP 目标判断。

## 6. P0: Must Exist For MVP

### Core Identity

以下能力定义 MedLearn 的 MVP 身份，必须存在：

- **Knowledge**：结构化医学知识是基础。
- **Case Simulator**：临床推理病例训练是终点。
- **Scoring / Feedback**：没有反馈，训练不会形成闭环。

Knowledge 与 Case Simulator 均可独立进入和完成。这里的“基础”和“终点”描述产品能力层级，不规定单次使用顺序。

### Core Access

以下能力不定义身份，但定义用户能否进入核心价值，必须存在：

- **Search**：Search 是进入 Knowledge 的入口。对用户而言，Knowledge without Search ≈ 不存在。

### Safety Baseline

以下安全要求必须存在：

- 明确教育用途，不提供真实患者诊疗建议。
- 病例标准答案、评分规则和审核信息由服务端保护。
- 病例内 AI 输出必须受 ground-truth 和安全检查约束。
- 医学安全、隐私和数据完整性优先于功能完整性。

## 7. P1: Next Stage

以下能力可以作为下一阶段增强，但不得仅因已经存在于代码中而自动成为 P0：

- **Learning Path**：帮助用户选择下一步学习内容。
- **Analytics**：帮助项目验证使用行为和学习闭环，但不是用户核心价值本身。
- **Spaced Repetition**：增强长期复习，但不是 MVP 身份核心。
- 更完整的病例恢复、病例质量状态管理、成本追踪和医学审核流程。

## 8. Experimental

以下能力可以保留为实验，但不得定义 MVP 核心：

- **Feynman**：属于 L1 Understanding 的实验性表达工具。
- **Generic AI Chat**：不得成为通用 ChatGPT 克隆；如果用于病例，必须收敛为受约束的病例内 Patient Interaction。

## 9. Explicit Non-goals

当前 MVP 不做：

- 真实患者诊疗支持；
- 临床决策支持；
- 医院或机构管理；
- 社区功能；
- 支付、订阅或商业化系统；
- 通用 AI Chat；
- 开放式 RAG 医学问答；
- 无人工审核的自动病例生成；
- 以技术展示为目的的 Agent、Benchmark 或知识图谱产品。

## 10. Success Metrics

MVP V2 的成功不以“功能数量”衡量，而以核心学习闭环是否成立衡量。

### Activation

- 用户能够通过 Search 找到并打开目标 Knowledge。
- 用户能够启动并完成至少一个 Case Simulator 流程。

### Learning Loop

- 用户完成病例后能够看到 Scoring / Feedback。
- Feedback 能指出一个明确、可修正的薄弱点。
- 用户愿意基于反馈继续一次修正或下一次病例训练。

### Retention / Repeat Use

- 用户在首次完成病例后愿意再次进入 Knowledge 或 Case Simulator。
- 第二次病例开始率和反馈后继续练习率优先于功能点击量。

### Safety / Quality

- 医学内容问题可被报告和追踪。
- 病例答案、评分规则和审核字段不暴露给客户端。
- 病例内 AI 不泄露诊断，不提供真实诊疗建议。

## 11. Architecture Principles

MVP V2 遵循 `docs/PROJECT_CONSTITUTION.md`：

- 代码 > 文档 > 记忆 > 聊天记录。
- Reality defines existence; validation defines importance; identity defines priority。
- active_object ≤ 1。
- 已经工作并被证据支持的系统，默认比未经验证的替代方案更有价值。
- 改变系统必须由医学安全、用户反馈、数据错误、上游变化或可复现缺陷驱动。
- Agent 的职责是延续项目，而不是接管项目。

## 12. Documentation Contract

新 Agent 在完全失忆的情况下，应能通过以下文件继续工作：

1. `docs/PROJECT_CONSTITUTION.md`：产品身份、原则和边界。
2. `docs/MVP_PRD_V2.md`：当前 MVP 范围和优先级。
3. `docs/CURRENT_STATE.md`：由状态 YAML 生成的当前执行状态。
4. `docs/ADR_INDEX.yaml`：ADR 机器可读索引。

如果这四个文件与聊天记录冲突，以这四个文件和仓库代码为准。

# MedLearn Project Constitution

## 1. Product Identity

> **MedLearn 是以结构化医学知识为基础的临床思维训练系统。**
>
> 书是基础。框架是核心。推理是终点。

MedLearn 服务于医学生和低年资住院医师，帮助学习者从结构化医学知识出发，建立临床框架，并通过病例训练形成可迁移的临床推理能力。

MedLearn 仅用于医学教育。它不是面向真实患者的诊断、治疗或临床决策支持系统。

## 2. Product Layers

MedLearn 的稳定能力层级是：

```text
L0 Knowledge
   ↓
L1 Understanding
   ↓
L2 Framework
   ↓
L3 Clinical Reasoning
```

- **L0 Knowledge**：教材、目录、搜索和知识详情。
- **L1 Understanding**：费曼复述、机制解释和概念关系。
- **L2 Framework**：症状学框架、VINDICATE、鉴别诊断方法和临床推理模板。
- **L3 Clinical Reasoning**：病例模拟、证据整合、诊疗决策和针对性复盘。

这些层级定义产品能力，不代表所有能力都属于当前 MVP。当前 MVP 范围以 `docs/MVP_PRD_V2.md` 为准；当前执行状态以 `state/*.yaml` 和生成的 `docs/CURRENT_STATE.md` 为准。

## 3. Priority Principle

> **Reality defines existence.**
>
> **Validation defines importance.**
>
> **Identity defines priority.**

翻译：

> **现实决定什么存在。**
>
> **验证决定什么重要。**
>
> **身份决定什么优先。**

代码存在，不代表：

- 用户需要；
- 已经验证；
- 应该进入 P0；
- 定义产品身份。

## 4. Reality Principle

当事实来源冲突时，优先级为：

```text
代码 > 文档 > 记忆 > 聊天记录
```

更具体地：

| 问题 | 优先事实来源 |
|---|---|
| 当前实现了什么 | 代码、自动化测试、数据库 migration、可复现运行结果 |
| 产品为什么存在 | `docs/PROJECT_CONSTITUTION.md` |
| 当前 MVP 要做什么 | `docs/MVP_PRD_V2.md` |
| 为什么采用某项设计 | 状态为 `accepted` 的 ADR |
| 当前正在做什么 | `state/*.yaml` 与生成的 `docs/CURRENT_STATE.md` |
| 用户真实需要什么 | 用户行为、原始反馈、Issue、Conversation |

文档声明不能覆盖相反的运行证据。代码也不能自行改变产品目标。

## 5. Core Product Boundary

### 5.1 Must Keep: Core Identity

以下能力定义 MedLearn 的产品身份，缺失后产品身份会被破坏：

- **Knowledge**：结构化医学知识是基础。
- **Case Simulator**：临床推理训练是终点。
- **Scoring / Feedback**：没有反馈，训练不会形成闭环。

### 5.2 Must Keep: Core Access

以下能力不定义身份，但定义用户能否进入核心价值：

- **Search**：Search 不是身份，但 Search 是进入 Knowledge 的入口。对用户而言，Knowledge without Search ≈ 不存在。

### 5.3 Nice To Have

以下能力可以增强产品，但不得仅因代码存在而自动进入 P0：

- Learning Path
- Analytics
- Spaced Repetition

### 5.4 Experimental

以下能力可以作为实验存在，但不得定义 MVP 核心，也不得绕过医学安全和产品边界：

- Feynman
- Generic AI Chat

## 6. Explicit Non-Identity

MedLearn 不是：

- ChatGPT 克隆；
- 通用 AI Chat；
- 真实患者诊疗系统；
- 临床决策支持系统；
- RAG、Agent 或 Benchmark 展示项目；
- 仅供展示的知识图谱系统。

结构化知识是基础设施，临床思维训练是产品价值。

## 7. Change Principle

> 已经工作并被证据支持的系统，默认比未经验证的替代方案更有价值。

改变系统必须由以下证据驱动：

- 医学安全或隐私问题；
- 用户行为或可追溯的用户反馈；
- 数据错误；
- 上游依赖或运行环境变化；
- 可复现的 bug、性能问题或工程缺陷；
- 当前 MVP 明确要求；
- 有效 ADR 明确授权。

禁止：

- 无证据重写；
- 为展示技术而扩大范围；
- 因技术潮流替换已工作的系统；
- 补全不存在的历史；
- 未经记录的大范围重构；
- 继续加功能来逃避产品收敛。

## 8. Active Object Principle

任意时刻：

```text
active_object ≤ 1
```

`state/*.yaml` 是项目运行状态的唯一结构化事实源。`docs/CURRENT_STATE.md` 只能由生成脚本产生，禁止手写。

对象状态只能是：

- `active`
- `paused`
- `blocked`
- `completed`
- `archived`

没有正在执行的对象时，`active_object` 应为 `null`，项目应处于可恢复稳定状态。

## 9. Agent Working Rules

Agent 的职责是延续项目，而不是接管项目。

新 Agent 在完全失忆的情况下，应先阅读：

1. `docs/PROJECT_CONSTITUTION.md`
2. `docs/MVP_PRD_V2.md`
3. `docs/CURRENT_STATE.md`
4. `docs/ADR_INDEX.yaml`
5. 与当前对象相关的 `state/*.yaml`

只有以下情况需要停下来询问：

- 可能影响医学正确性或患者安全；
- 可能暴露隐私或敏感信息；
- 需要删除、覆盖或不可逆迁移数据；
- 证据之间存在无法从仓库消解的冲突；
- 用户意图缺失会导致高风险或方向性错误。

普通实现细节应优先从仓库发现，并采用可逆、保守、符合现有模式的方案。

## 10. ADR Discipline

`docs/ADR_INDEX.yaml` 是 ADR 的机器可读索引。

Agent 不按时间批量读取 ADR，而是：

1. 读取 ADR Index；
2. 根据 Active Object 的 ID、范围和标签筛选相关 ADR；
3. 只加载状态为 `accepted` 且确实适用的决策；
4. 对 `proposed` ADR 只作为待决信息，不视为已生效约束。

ADR 必须记录适用范围、状态、路径和替代关系。不存在的历史决策不得补写成 ADR。

## 11. Medical Safety

- 教材和经审核病例是医学内容的主要事实来源。
- 禁止猜测教材目录、章节或医学事实。
- AI 输出必须明确保持教育用途，不得用于真实患者诊疗。
- 病例标准答案、评分规则和审核信息必须由服务端保护。
- 医学测试通过不等于医学审核通过。
- 模型、提示词、评分规则或病例内容改变后，必须重新进行相应回归测试和医学抽样。
- 医学安全、隐私和数据完整性不受“用户价值优先”或“项目惯性”豁免。

## 12. Display And Meaning

显示层级和语义关系必须分离：

```text
显示层级：书 -> 章节 -> 小节
语义关系：并发症、鉴别诊断、检查、治疗、机制等
```

目录不得被推断成语义图谱，语义关系也不得改写教材目录。

# MedLearn 后端接口文档

**版本**: 1.0  
**日期**: 2026-06-02  
**对应 PRD**: v2.0  

---

## 目录

1. [接口概览](#1-接口概览)
2. [云函数接口](#2-云函数接口)
3. [云数据库直访接口](#3-云数据库直访接口)
4. [AI 服务接口](#4-ai-服务接口)
5. [数据集合参考](#5-数据集合参考)

---

## 1. 接口概览

### 1.1 接口分类

MedLearn 后端接口分为三类：

| 类型 | 调用方式 | 适用场景 |
|------|----------|----------|
| **云函数** | `wx.cloud.callFunction()` | 需要服务端执行的业务逻辑（登录、事务、分析） |
| **云数据库直访** | `cloud.ts` 封装层 | 单表 CRUD 操作（前端直接读写云数据库） |
| **AI 服务** | `Taro.request()` 直连 | AI 评估/生成（客户端直连 AI API） |

### 1.2 通用响应格式

**云函数统一响应格式**：

```typescript
interface CloudFunctionResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}
```

**云数据库直访响应格式**：

```typescript
interface DBQueryResponse {
  data: any[];
}

interface DBAddResponse {
  _id: string;
}

interface DBUpdateResponse {
  stats: { updated: number };
}

interface DBCountResponse {
  total: number;
}
```

### 1.3 认证方式

| 接口类型 | 认证方式 | 说明 |
|----------|----------|------|
| 云函数 | 自动注入 `_openid` | 云函数通过 `cloud.getWXContext().OPENID` 获取用户身份 |
| 云数据库直访 | 安全规则 `_openid` 匹配 | 云数据库安全规则限制用户只能读写自己的数据 |
| AI 服务 | API Key | 用户在设置页配置，存储在 `wx.Storage`，通过 HTTP Header 传递 |

---

## 2. 云函数接口

### 2.1 initUser — 微信登录

**功能**：微信登录 code 换取 openid，新用户自动创建记录

**调用方式**：

```typescript
const result = await wx.cloud.callFunction({
  name: 'initUser',
  data: { code: string }
});
```

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | ✅ | `Taro.login()` 获取的微信登录凭证 |

**响应参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| openid | string | 用户唯一标识（成功时返回） |
| isNewUser | boolean | 是否新用户 |
| error | string | 错误信息（失败时返回） |

**响应示例**：

```json
{
  "success": true,
  "openid": "oXXXXXXXXXXXXXXXX",
  "isNewUser": true
}
```

**业务逻辑**：

1. 调用 `cloud.openapi.auth.code2Session({ code })` 换取 openid
2. 查询 `users` 集合是否已有该 openid 的记录
3. 新用户：创建记录（含 `createdAt`、`lastLoginAt`、`settings`）
4. 老用户：更新 `lastLoginAt`
5. 返回 openid + isNewUser 标志

**错误码**：

| 错误信息 | 原因 |
|----------|------|
| `Failed to get openid` | code 无效或过期 |
| `Unknown error` | 微信 API 调用异常 |

---

### 2.2 initSeedData — 种子数据初始化

**功能**：首次登录时写入 800+ 知识点、36 道考题、34 条推导链、7 个病例

**调用方式**：

```typescript
const result = await wx.cloud.callFunction({
  name: 'initSeedData',
  data: {}
});
```

**请求参数**：无

**响应参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| skipped | boolean | 是否跳过（数据已存在） |
| knowledgeCount | number | 写入知识点数量 |
| questionCount | number | 写入考题数量 |
| chainCount | number | 写入推导链数量 |
| caseCount | number | 写入病例数量 |
| error | string | 错误信息 |

**响应示例**：

```json
{
  "success": true,
  "knowledgeCount": 812,
  "questionCount": 36,
  "chainCount": 34,
  "caseCount": 7
}
```

**业务逻辑**：

1. 检查 `knowledge_nodes` 集合是否已有数据，有则返回 `skipped: true`
2. 从 `data/` 目录读取 6 个 JSON 文件
3. 三个知识点数据源按 `id` 去重合并
4. 分批写入（每批 20 条并发），写入 4 个集合：
   - `knowledge_nodes`（小写）
   - `exam_questions`（小写）
   - `causal_chains`（小写）
   - `cases`（小写）

**注意事项**：

- 集合名使用小写下划线格式，与前端 `COLLECTIONS` 常量一致
- 800+ 条数据分批写入，耗时约 10-30 秒
- 此云函数由服务端调用，不依赖用户 openid

---

### 2.3 submitExam — 考试提交

**功能**：考试提交事务，原子写入 4 张表

**调用方式**：

```typescript
const result = await wx.cloud.callFunction({
  name: 'submitExam',
  data: {
    session: ExamSessionData,
    records: ExamRecordData[],
    wrongQuestions: WrongQuestionData[],
    activity: StudyActivityData
  }
});
```

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session | object | ✅ | 考试会话数据 |
| records | array | ✅ | 答题记录数组 |
| wrongQuestions | array | ❌ | 错题数组（可为空） |
| activity | object | ✅ | 学习活动记录 |

**session 结构**：

```typescript
{
  subject: string;          // 考试科目
  totalQuestions: number;   // 总题数
  correctCount: number;     // 正确数
  score: number;            // 得分
  startTime: number;        // 开始时间戳
  endTime: number;          // 结束时间戳
  weakNodes: string[];      // 薄弱知识点 ID 列表
}
```

**records 数组元素结构**：

```typescript
{
  questionId: string;           // 题目 ID
  selectedAnswers: string[];    // 用户选择
  isCorrect: boolean;           // 是否正确
  timeSpent: number;            // 用时(ms)
  relatedKnowledgeIds: string[]; // 关联知识点 ID
}
```

**wrongQuestions 数组元素结构**：

```typescript
{
  questionId: string;           // 题目 ID
  nodeId: string;               // 关联知识点 ID
  userAnswer: string[];         // 用户答案
  correctAnswer: string[];      // 正确答案
  retryCorrect: boolean;        // 重做是否正确
}
```

**activity 结构**：

```typescript
{
  type: 'exam';                 // 活动类型
  duration: number;             // 用时(ms)
  date: string;                 // 日期 YYYY-MM-DD
  createdAt: number;            // 时间戳
}
```

**响应参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| results.sessionId | string | 考试会话记录 ID |
| results.recordCount | number | 答题记录数量 |
| results.wrongQuestionCount | number | 错题数量 |

**响应示例**：

```json
{
  "success": true,
  "results": {
    "sessionId": "abc123",
    "recordCount": 10,
    "wrongQuestionCount": 3
  }
}
```

**注意事项**：

- 4 张表写入非真正事务（云数据库不支持跨集合事务），如中间步骤失败，前面写入不会回滚
- 错题数组可选，答全对时传空数组或不传

---

### 2.4 analytics — 数据分析

**功能**：服务端计算掌握度地图、薄弱知识点、学习活动时间线

**调用方式**：

```typescript
const result = await wx.cloud.callFunction({
  name: 'analytics',
  data: {
    action: 'getMasteryMap' | 'getWeakPoints' | 'getActivityTimeline',
    days?: number
  }
});
```

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | ✅ | 操作类型 |
| days | number | ❌ | 天数（仅 getActivityTimeline 使用，默认 30） |

#### 2.4.1 action: getMasteryMap

**功能**：计算每个知识点的掌握度评分

**掌握度公式**：

```
mastery = Feynman(40%) + Pathway(30%) + Exam(30%)
```

| 维度 | 权重 | 数据来源 | 计算方式 |
|------|------|----------|----------|
| Feynman | 40% | `feynman_records` | 同一知识点所有费曼评分的平均值 × 0.4 |
| Pathway | 30% | `learning_records`（type=pathway） | 同一知识点推导链准确率的平均值 × 0.3 × 100 |
| Exam | 30% | `exam_records` | 关联题目正确率 × 0.3 × 100 |

**响应 data 结构**：

```typescript
Array<{
  nodeId: string;          // 知识点 ID
  nodeTitle: string;       // 知识点标题
  subject: string;         // 所属学科
  mastery: number;         // 掌握度评分（0-100）
  componentCount: number;  // 有数据的维度数（0-3）
}>
```

**响应示例**：

```json
{
  "success": true,
  "data": [
    { "nodeId": "pneumonia", "nodeTitle": "肺炎", "subject": "内科学 - 呼吸系统疾病", "mastery": 72, "componentCount": 3 },
    { "nodeId": "asthma", "nodeTitle": "哮喘", "subject": "内科学 - 呼吸系统疾病", "mastery": 0, "componentCount": 0 }
  ]
}
```

#### 2.4.2 action: getWeakPoints

**功能**：获取掌握度 < 40 的薄弱知识点，按掌握度升序排列，最多 20 个

**响应 data 结构**：同 getMasteryMap，但仅包含 mastery < 40 的项

#### 2.4.3 action: getActivityTimeline

**功能**：获取最近 N 天的学习活动时间线

**响应 data 结构**：

```typescript
Array<{
  date: string;     // 日期 YYYY-MM-DD
  minutes: number;  // 学习时长（分钟）
  count: number;    // 学习次数
}>
```

**响应示例**：

```json
{
  "success": true,
  "data": [
    { "date": "2026-05-30", "minutes": 25, "count": 3 },
    { "date": "2026-05-31", "minutes": 40, "count": 5 }
  ]
}
```

**注意事项**：

- 所有动态数据查询已添加 `_openid` 过滤，确保数据隔离
- `knowledge_nodes` 为静态数据，不按 openid 过滤
- `getActivityTimeline` 使用 `db.command.gte` 做复合条件查询

---

### 2.5 completePathway — 推导链完成记录

**功能**：保存推导链完成记录 + 学习活动

**调用方式**：

```typescript
const result = await wx.cloud.callFunction({
  name: 'completePathway',
  data: {
    learningRecord: LearningRecordData,
    activity: StudyActivityData
  }
});
```

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| learningRecord | object | ✅ | 学习记录 |
| activity | object | ✅ | 学习活动 |

**learningRecord 结构**：

```typescript
{
  type: 'pathway';               // 记录类型
  targetId: string;              // 推导链 ID
  accuracy: number;              // 准确率（0-1）
  totalSteps: number;            // 总步数
  correctSteps: number;          // 正确步数
  mistakes: Mistake[];           // 错误详情
  startTime: number;             // 开始时间戳
  endTime: number;               // 结束时间戳
}
```

**activity 结构**：

```typescript
{
  type: 'pathway';
  targetId: string;              // 推导链 ID
  duration: number;              // 用时(ms)
  date: string;                  // 日期 YYYY-MM-DD
  createdAt: number;             // 时间戳
}
```

**响应参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| recordId | string | 学习记录 ID |
| activityId | string | 活动记录 ID |

---

### 2.6 saveGeneratedContent — AI 生成内容保存

**功能**：保存 AI 生成的知识节点、推导链或病例

**调用方式**：

```typescript
const result = await wx.cloud.callFunction({
  name: 'saveGeneratedContent',
  data: {
    nodes?: KnowledgeNode[],
    chain?: CausalChain,
    case?: MedicalCase
  }
});
```

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nodes | array | ❌ | AI 生成的知识节点数组 |
| chain | object | ❌ | AI 生成的推导链 |
| case | object | ❌ | AI 生成的病例 |

> 三个参数至少传一个。

**响应参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| results.nodeCount | number | 保存的知识节点数量 |
| results.chainId | string | 推导链记录 ID |
| results.caseId | string | 病例记录 ID |

---

### 2.7 deleteUserData — 账户注销（新增）

**功能**：删除用户所有个人数据，满足《个人信息保护法》要求

**调用方式**：

```typescript
const result = await wx.cloud.callFunction({
  name: 'deleteUserData',
  data: {}
});
```

**请求参数**：无（openid 通过 `cloud.getWXContext()` 自动获取）

**响应参数**：

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| totalDeleted | number | 总删除记录数 |
| details | object | 每个集合的删除数量 |

**响应示例**：

```json
{
  "success": true,
  "totalDeleted": 156,
  "details": {
    "learning_records": 12,
    "feynman_records": 45,
    "case_records": 3,
    "exam_records": 30,
    "exam_sessions": 5,
    "dialogue_records": 28,
    "wrong_questions": 15,
    "study_activities": 18,
    "spaced_repetition": 0,
    "settings": 0,
    "favorites": 0,
    "learning_paths": 0,
    "study_plans": 0,
    "study_goals": 0
  }
}
```

**删除范围**（14 个集合）：

| 集合 | 说明 |
|------|------|
| learning_records | 学习记录 |
| feynman_records | 费曼复述记录 |
| case_records | 病例练习记录 |
| exam_records | 答题记录 |
| exam_sessions | 考试会话 |
| dialogue_records | 对话记录 |
| wrong_questions | 错题 |
| study_activities | 学习活动 |
| spaced_repetition | 间隔重复计划 |
| settings | 用户设置 |
| favorites | 收藏 |
| learning_paths | 学习路径 |
| study_plans | 学习计划 |
| study_goals | 学习目标 |

**注意事项**：

- 不删除 `knowledge_nodes`、`exam_questions`、`causal_chains`、`cases` 等静态种子数据
- 不删除 `users` 集合中的用户记录（仅清除关联数据）
- 分页删除（每页 100 条），每页内并发删除
- 建议前端实现 7 天冷静期机制

---

## 3. 云数据库直访接口

前端通过 `cloud.ts` 封装层直接访问云数据库，不经过云函数。

### 3.1 queryCollection — 条件查询

```typescript
queryCollection(collectionName: string, options?: {
  where?: Record<string, any>;
  orderBy?: { field: string; direction: 'asc' | 'desc' };
  limit?: number;
  skip?: number;
}): Promise<any[]>
```

**参数说明**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| collectionName | string | ✅ | 集合名（使用 `COLLECTIONS` 常量） |
| options.where | object | ❌ | 查询条件 |
| options.orderBy | object | ❌ | 排序 |
| options.limit | number | ❌ | 限制数量（默认 20，最大 100） |
| options.skip | number | ❌ | 跳过数量 |

**返回值**：记录数组，失败返回 `[]`

### 3.2 queryAll — 分页遍历全部记录

```typescript
queryAll(collectionName: string, where?: Record<string, any>): Promise<any[]>
```

**说明**：自动分页遍历（每页 100 条），返回所有匹配记录。适用于数据量较大的场景。

### 3.3 getById — 按 ID 获取单条

```typescript
getById(collectionName: string, id: string): Promise<any | null>
```

### 3.4 addRecord — 新增单条

```typescript
addRecord(collectionName: string, data: Record<string, any>): Promise<string>
```

**返回值**：新记录的 `_id`

### 3.5 addBatch — 批量新增

```typescript
addBatch(collectionName: string, records: Record<string, any>[]): Promise<number>
```

**说明**：每批 20 条 `Promise.allSettled` 并发写入，返回成功写入的数量。

### 3.6 updateRecord — 更新记录

```typescript
updateRecord(collectionName: string, id: string, data: Record<string, any>): Promise<boolean>
```

**返回值**：是否更新成功

### 3.7 countRecords — 计数

```typescript
countRecords(collectionName: string, where?: Record<string, any>): Promise<number>
```

### 3.8 hasRecords — 是否有记录

```typescript
hasRecords(collectionName: string): Promise<boolean>
```

---

## 4. AI 服务接口

AI 服务通过 `ai.ts` 实现客户端直连 AI API，不经过云函数。

### 4.1 配置管理

#### getAIConfig — 获取 AI 配置

```typescript
getAIConfig(): { apiKey: string; baseUrl: string; model: string }
```

**说明**：从 `wx.Storage` 读取配置，未配置时返回默认值。

| 字段 | 默认值 |
|------|--------|
| apiKey | `''` |
| baseUrl | `'https://api.openai.com'` |
| model | `'gpt-4o'` |

#### setAIConfig — 保存 AI 配置

```typescript
setAIConfig(config: Partial<{ apiKey: string; baseUrl: string; model: string }>): void
```

**说明**：部分更新，仅更新传入的字段。

### 4.2 AI 评估函数

#### evaluateFeynman — 费曼复述评估

```typescript
evaluateFeynman(
  nodeTitle: string,
  nodeContent: string,
  keyPoints: string[],
  explanation: string
): Promise<{ content: string; evaluation: FeynmanEvaluation }>
```

**请求参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| nodeTitle | string | 知识点标题 |
| nodeContent | string | 知识点内容 |
| keyPoints | string[] | 参考要点 |
| explanation | string | 用户复述文本 |

**evaluation 结构**：

```typescript
{
  score: number;              // 0-100
  understood: string[];       // 已理解的要点
  gaps: string[];             // 未理解或遗漏的内容
  strengths: string[];        // 做得好的地方
  suggestion: string;         // 学习建议
  followUpQuestions: string[]; // 追问问题
}
```

**API 参数**：temperature = 0.5

---

#### evaluateVindicate — VINDICATE 鉴别诊断评估

```typescript
evaluateVindicate(
  nodeTitle: string,
  nodeContent: string,
  categories: Record<string, string>
): Promise<{ content: string; evaluation: VindicateEvaluation }>
```

**请求参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| nodeTitle | string | 知识点标题 |
| nodeContent | string | 知识点内容 |
| categories | Record<string, string> | VINDICATE 各类别用户输入，key 为 V/I/N/D/I2/C/A/T/E |

**evaluation 结构**：

```typescript
{
  score: number;                          // 0-100
  categoryEvaluations: {
    [key: string]: {
      correct: boolean;
      feedback: string;
    }
  };
  missedCategories: string[];             // 遗漏的类别
  overallFeedback: string;                // 总体评价
  suggestion: string;                     // 改进建议
}
```

**API 参数**：temperature = 0.5

---

#### evaluateDiagnosis — 病例诊断评估

```typescript
evaluateDiagnosis(
  caseTitle: string,
  correctDiagnosis: string,
  userDiagnosis: string
): Promise<{ content: string; evaluation: DiagnosisEvaluation }>
```

**evaluation 结构**：

```typescript
{
  isCorrect: boolean;
  accuracy: number;           // 0-100
  feedback: string;
  missedPoints: string[];
  teachingNote: string;
}
```

**API 参数**：temperature = 0.3

---

#### evaluateTreatment — 治疗方案评估

```typescript
evaluateTreatment(
  caseTitle: string,
  correctTreatment: string,
  userTreatment: string
): Promise<{ content: string; evaluation: TreatmentEvaluation }>
```

**evaluation 结构**：同 evaluateDiagnosis

**API 参数**：temperature = 0.3

---

#### continueLearningDialogue — 苏格拉底式对话

```typescript
continueLearningDialogue(
  nodeTitle: string,
  nodeContent: string,
  history: Message[],
  newMessage: string
): Promise<string>
```

**请求参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| nodeTitle | string | 知识点标题 |
| nodeContent | string | 知识点内容 |
| history | Message[] | 对话历史 |
| newMessage | string | 用户新消息 |

**Message 结构**：

```typescript
{ role: 'user' | 'assistant' | 'system'; content: string }
```

**返回值**：AI 回复文本。当 AI 检测到用户已掌握时，回复以 `[MASTERY_DETECTED]` 开头。

**API 参数**：temperature = 0.7, maxTokens = 1024

---

### 4.3 AI 生成函数

#### generateCausalChain — 生成推导链

```typescript
generateCausalChain(topic: string): Promise<CausalChainData | null>
```

**返回结构**：

```typescript
{
  title: string;
  subject: string;
  chapter: string;
  description: string;
  steps: Array<{
    stepNumber: number;
    scenario: string;
    question: string;
    options: Array<{
      text: string;
      isCorrect: boolean;
      consequence: string;
      reasoning: string;
    }>;
  }>;
  learningObjectives: string[];
}
```

**API 参数**：temperature = 0.7, maxTokens = 4096

---

#### generateMedicalCase — 生成病例

```typescript
generateMedicalCase(topic: string, difficulty?: number): Promise<MedicalCaseData | null>
```

**请求参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| topic | string | 病例主题 |
| difficulty | number | 难度（1-3，默认 2） |

**API 参数**：temperature = 0.8, maxTokens = 4096

---

#### extractComparisonDimensions — 疾病对比

```typescript
extractComparisonDimensions(
  diseaseA: string,
  diseaseB: string,
  contentA: string,
  contentB: string
): Promise<{ dimensions: ComparisonDimension[] }>
```

**请求参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| diseaseA | string | 疾病 A 名称 |
| diseaseB | string | 疾病 B 名称 |
| contentA | string | 疾病 A 教材内容（截取前 2000 字） |
| contentB | string | 疾病 B 教材内容（截取前 2000 字） |

**返回结构**：

```typescript
{
  dimensions: Array<{
    name: string;       // 维度名称（如：病因）
    valueA: string;     // 疾病 A 的值
    valueB: string;     // 疾病 B 的值
    isSame: boolean;    // 是否相同
  }>
}
```

**API 参数**：temperature = 0.3, maxTokens = 2048

---

### 4.4 工具函数

#### fetchModels — 获取可用模型列表

```typescript
fetchModels(baseUrl?: string, apiKey?: string): Promise<string[]>
```

**说明**：调用 `/v1/models` 获取模型列表，过滤掉 instruct/embedding/moderation 类型。失败时返回空数组。

#### testConnection — 测试 AI 连接

```typescript
testConnection(): Promise<{ success: boolean; message: string; models?: string[] }>
```

**说明**：先尝试拉取模型列表，失败则发一个简单测试请求。

---

### 4.5 AI 调用底层机制

#### 双 API 格式自动检测

| URL 模式 | API 格式 | 端点 | 认证方式 |
|----------|----------|------|----------|
| 包含 `anthropic.com` 或 `api.meai.cloud/claude` | Anthropic Messages API | `/v1/messages` | `x-api-key` + `anthropic-version: 2023-06-01` |
| 其他 | OpenAI 兼容接口 | `/v1/chat/completions` | `Authorization: Bearer {key}` |

#### 超时处理

| 阶段 | 前端行为 |
|------|----------|
| 0-3s | 展示评估框架骨架 |
| 15s+ | 展示"🤔 AI 正在深度分析中"提示 + 取消按钮 |
| 30s+ | 展示超时错误 + 重新提交按钮 |
| 默认超时 | 60 秒（`Taro.request` timeout 参数） |

#### 响应解析

AI 返回文本后，`extractJson()` 尝试从以下格式提取 JSON：
1. ` ```json ... ``` ` 代码块
2. 裸 JSON 对象 `{ ... }`

解析失败时返回 fallback 结构（如费曼评估返回 `score: 0, gaps: ['无法解析评估结果']`）。

---

## 5. 数据集合参考

### 5.1 集合名常量

```typescript
export const COLLECTIONS = {
  KNOWLEDGE_NODES: 'knowledge_nodes',
  CAUSAL_CHAINS: 'causal_chains',
  CASES: 'cases',
  LEARNING_RECORDS: 'learning_records',
  FEYNMAN_RECORDS: 'feynman_records',
  CASE_RECORDS: 'case_records',
  EXAM_QUESTIONS: 'exam_questions',
  EXAM_RECORDS: 'exam_records',
  EXAM_SESSIONS: 'exam_sessions',
  SETTINGS: 'settings',
  DIALOGUE_RECORDS: 'dialogue_records',
  WRONG_QUESTIONS: 'wrong_questions',
  FAVORITES: 'favorites',
  STUDY_ACTIVITIES: 'study_activities',
  SPACED_REPETITION: 'spaced_repetition',
  LEARNING_PATHS: 'learning_paths',
  STUDY_PLANS: 'study_plans',
  STUDY_GOALS: 'study_goals',
} as const;
```

### 5.2 集合分类

#### 静态数据（种子数据，初始化后极少变化）

| 集合 | 数据量 | 写入方式 |
|------|--------|----------|
| knowledge_nodes | 800+ | initSeedData 云函数 / seedData.ts 客户端 |
| exam_questions | 36 | 同上 |
| causal_chains | 34 | 同上 |
| cases | 7 | 同上 |

#### 动态数据（用户产生，持续增长）

| 集合 | 写入方式 | 读取方式 |
|------|----------|----------|
| learning_records | completePathway 云函数 | queryCollection |
| feynman_records | addRecord 直写 | queryCollection |
| case_records | addRecord 直写 | queryCollection |
| exam_records | submitExam 云函数 | queryCollection |
| exam_sessions | submitExam 云函数 | queryCollection |
| dialogue_records | addRecord 直写 | queryCollection |
| wrong_questions | submitExam 云函数 / addRecord | queryCollection |
| study_activities | 云函数 / addRecord | analytics 云函数 / queryCollection |
| spaced_repetition | addRecord / updateRecord | queryCollection / countRecords |
| settings | addRecord / updateRecord | queryCollection |
| favorites | addRecord / updateRecord | queryCollection |
| learning_paths | addRecord / updateRecord | queryCollection |
| study_plans | addRecord / updateRecord | queryCollection |
| study_goals | addRecord / updateRecord | queryCollection |

### 5.3 安全规则

| 集合类型 | 读权限 | 写权限 |
|----------|--------|--------|
| 静态数据 | 所有已登录用户 | 仅云函数 |
| 动态数据 | 仅记录所有者（`_openid` 匹配） | 仅记录所有者 |

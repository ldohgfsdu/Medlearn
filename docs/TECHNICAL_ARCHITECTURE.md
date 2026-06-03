# MedLearn 技术架构文档

**版本**: 1.0  
**日期**: 2026-06-02  
**对应 PRD**: v2.0  

---

## 目录

1. [架构总览](#1-架构总览)
2. [前端架构](#2-前端架构)
3. [后端架构（云开发）](#3-后端架构云开发)
4. [数据模型](#4-数据模型)
5. [功能-模块映射](#5-功能-模块映射)
6. [核心流程](#6-核心流程)
7. [分包策略](#7-分包策略)
8. [技术债务](#8-技术债务)

---

## 1. 架构总览

### 1.1 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                     微信小程序前端                         │
│                                                          │
│  Pages ──→ Hooks ──→ Services ──→ Taro API / wx API      │
│                                                          │
└──────────┬──────────────┬──────────────┬─────────────────┘
           │              │              │
           ▼              ▼              ▼
    ┌────────────┐ ┌────────────┐ ┌────────────┐
    │  AI API    │ │  云数据库   │ │ wx.Storage │
    │ (客户端直连)│ │ (18 集合)  │ │ (本地缓存) │
    └────────────┘ └──────┬─────┘ └────────────┘
                          │
                    ┌─────▼──────┐
                    │   云函数    │
                    │  (6 个)    │
                    └────────────┘
```

### 1.2 前后端分离原则

| 层 | 职责 | 技术实现 |
|----|------|----------|
| **前端（小程序）** | UI 渲染、用户交互、路由管理、本地缓存、AI 请求发起 | Taro 4 + React 18 + TypeScript |
| **后端（云开发）** | 数据持久化、用户认证、业务逻辑事务 | 云数据库 + 云函数 |

**分离边界**：
- 前端通过 `Taro.request` 直连 AI API（V1.0），不经过云函数
- 前端通过 `cloud.ts` 封装层访问云数据库，不直接操作数据库
- 云函数仅处理需要服务端执行的业务逻辑（登录、考试提交、数据分析）
- AI 评估逻辑在前端组装 Prompt，通过 `ai.ts` 发起请求，结果由前端解析和展示

### 1.3 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 前端框架 | Taro | 4.x |
| UI 框架 | React | 18.x |
| 语言 | TypeScript | 5.x |
| 样式 | SCSS Modules | — |
| 构建 | Webpack5 | 5.x |
| 后端 | 微信云开发 | 基础库 3.16.1 |
| AI | Anthropic / OpenAI 兼容 | — |

---

## 2. 前端架构

### 2.1 目录结构

```
src/
├── app.config.ts              # 路由、TabBar、分包、窗口配置
├── app.tsx                    # 应用入口（登录、种子数据初始化）
├── app.scss                   # 全局样式
│
├── pages/                     # 主包 TabBar 页面
│   ├── home/                  # 首页（学习仪表盘）
│   ├── feynman/               # 知识地图
│   ├── clinic-sandbox/        # 病例沙盒
│   └── profile/               # 我的
│
├── pagesA/                    # 分包 A
│   ├── feynman-detail/        # 知识点详情（费曼/VINDICATE/对话）
│   ├── case-detail/           # 病例模拟详情
│   └── pathway/               # 推导链
│
├── pagesB/                    # 分包 B
│   ├── setup/                 # 初始设置
│   ├── exam/                  # 模拟考试
│   ├── compare-mode/          # 疾病对比
│   ├── wrong-questions/       # 错题本
│   ├── study-calendar/        # 学习日历
│   ├── settings/              # API 配置
│   └── learning-hub/          # 学习中心
│
├── components/
│   ├── common/                # 通用组件
│   │   ├── StreamingContent   # 打字机效果
│   │   ├── ECharts            # 图表
│   │   ├── Skeleton           # 骨架屏
│   │   ├── ConfirmDialog      # 确认弹窗
│   │   ├── ErrorBoundary      # 错误边界
│   │   ├── LoadingSpinner     # 加载动画
│   │   └── Toast              # 轻提示
│   └── icons/                 # 图标组件
│
├── services/                  # 服务层（前后端交互边界）
│   ├── ai.ts                  # AI 调用（直连 API）
│   ├── auth.ts                # 认证
│   ├── cloud.ts               # 云数据库封装
│   ├── cache.ts               # 本地缓存
│   ├── seedData.ts            # 种子数据初始化
│   └── knowledgeGrouping.ts   # 知识点分组算法
│
├── hooks/                     # 数据 Hooks
│   ├── useStaticData.ts       # 静态数据（cache-first）
│   └── useCloudQuery.ts       # 动态数据（cache-then-cloud）
│
├── constants/                 # 常量
│   ├── subjects.ts            # 8 大系统定义
│   ├── internalMedicineCatalog.ts  # 内科学目录
│   ├── textbookCatalog.ts     # 教材目录
│   └── vindicate.ts           # VINDICATE 框架定义（待创建）
│
├── types/                     # TypeScript 类型
│   ├── knowledge.ts           # KnowledgeNode / CausalChain
│   ├── case.ts                # MedicalCase
│   ├── exam.ts                # ExamQuestion
│   ├── learning.ts            # 学习记录类型
│   └── index.ts               # 统一导出
│
├── data/                      # 种子数据
│   ├── seedKnowledge.ts       # 知识点（222 条）
│   ├── extractedKnowledge.ts  # 知识点 v6（483 条）
│   ├── extractedKnowledgeNodes.ts  # 知识点 v7（258 条）
│   ├── seedExamQuestions.ts   # 考题（36 道）
│   ├── seedPathways.ts        # 推导链（34 条）
│   └── seedCases.ts           # 病例（7 个）
│
└── utils/                     # 工具函数
    ├── index.ts               # 通用工具
    ├── spacedRepetition.ts    # SM-2 算法
    └── textbookDimensions.ts  # 教材维度工具
```

### 2.2 页面路由

| 路径 | TabBar | 功能 | PRD 功能 |
|------|--------|------|----------|
| `pages/home/index` | 学习 | 首页仪表盘 | F-P1-05 |
| `pages/feynman/index` | 知识 | 知识地图 | F-P0-01 |
| `pages/clinic-sandbox/index` | 病例 | 病例沙盒 | F-P0-05 |
| `pages/profile/index` | 我的 | 个人中心 | F-P0-07 |
| `pagesA/feynman-detail/index` | — | 费曼复述 + VINDICATE + 对话 | F-P0-02 / F-P0-03 / F-P0-04 |
| `pagesA/case-detail/index` | — | 病例模拟流程 | F-P0-05 |
| `pagesA/pathway/index` | — | 推导链 | F-P1-04 |
| `pagesB/exam/index` | — | 模拟考试 | F-P1-01 |
| `pagesB/compare-mode/index` | — | 疾病对比 | F-P1-03 |
| `pagesB/wrong-questions/index` | — | 错题本 | F-P1-01 |
| `pagesB/study-calendar/index` | — | 学习日历 | F-P2-03 |
| `pagesB/settings/index` | — | API 配置 | F-P1-06 |
| `pagesB/learning-hub/index` | — | 学习中心 | F-P1-05 |
| `pagesB/setup/index` | — | 初始设置 | F-P0-07 |

### 2.3 服务层设计

服务层是前端与后端的交互边界，所有外部数据访问必须经过服务层。

#### 2.3.1 ai.ts — AI 调用服务

```
ai.ts
├── getAIConfig()              # 读取 AI 配置（从 settings 集合 / 本地缓存）
├── setAIConfig(config)        # 保存 AI 配置
├── fetchModels(baseUrl, key)  # 获取可用模型列表
├── testConnection(config)     # 测试 API 连接
├── evaluateFeynman(node, transcript)       # 费曼复述评估
├── evaluateVindicate(node, categories)     # VINDICATE 评估
├── evaluateDiagnosis(case, diagnosis)      # 病例诊断评估
├── evaluateTreatment(case, treatment)      # 治疗方案评估
├── continueLearningDialogue(node, history) # 苏格拉底式对话
├── generateCausalChain(node)               # 生成推导链
├── generateMedicalCase(params)             # 生成病例
└── extractComparisonDimensions(node1, node2) # 疾病对比
```

**AI 调用流程**：

```
页面组件 → ai.ts 函数 → 组装 Prompt → Taro.request → AI API
                                                       ↓
页面组件 ← 解析响应 ← StreamingContent 打字机渲染 ← 完整 JSON 响应
```

**双 API 格式自动检测**：
- URL 含 `anthropic.com` → Anthropic Messages API（`x-api-key` + `anthropic-version`）
- 其他 → OpenAI 兼容接口（`Bearer` token）

**超时处理**：
- 15 秒：展示"🤔 AI 正在深度分析中"提示 + 取消按钮
- 30 秒：展示超时错误 + 重新提交按钮
- 取消后已输入内容保留

#### 2.3.2 cloud.ts — 云数据库封装

```
cloud.ts
├── 集合名常量（18 个）
├── query(collection, conditions, options)  # 查询
├── queryById(collection, id)               # 按 ID 查询
├── add(collection, data)                   # 新增
├── addBatch(collection, dataList)          # 批量新增（每批 20 条）
├── update(collection, id, data)            # 更新
├── remove(collection, id)                  # 删除
├── count(collection, conditions)           # 计数
└── queryPage(collection, conditions, page, pageSize)  # 分页查询
```

#### 2.3.3 cache.ts — 本地缓存

```
cache.ts
├── get(key)                  # 读取缓存
├── set(key, data, version?)  # 写入缓存（带版本号）
├── remove(key)               # 删除缓存
├── getVersion(key)           # 获取缓存版本
└── isExpired(key, ttl)       # 检查是否过期
```

底层使用 `Taro.getStorageSync` / `Taro.setStorageSync`。

#### 2.3.4 seedData.ts — 种子数据初始化

```
seedData.ts
└── initSeedData(openid)      # 首次登录初始化种子数据
    ├── 检查 knowledge_nodes 是否已有数据
    ├── 合并 3 个知识点源（按 id 去重）
    ├── 分批写入 knowledge_nodes（每批 20 条）
    ├── 写入 exam_questions（36 条）
    ├── 写入 causal_chains（34 条）
    └── 写入 cases（7 条）
```

### 2.4 数据 Hooks

| Hook | 策略 | 适用数据 |
|------|------|----------|
| `useStaticData` | cache-first：优先读缓存 → 缓存不存在查云端 → 写入缓存 | knowledge_nodes, exam_questions, causal_chains, cases |
| `useCloudQuery` | cache-then-cloud：先展示缓存 → 后台查云端 → 一致不更新 UI | learning_records, feynman_records, dialogue_records 等 |

**选择理由**：静态数据 800+ 条、变化极少，反复查云端浪费且会闪；动态数据需反映最新状态但不能乐观更新。

### 2.5 通用组件

| 组件 | 用途 | 对应 PRD 功能 |
|------|------|---------------|
| `StreamingContent` | AI 响应打字机效果（30-50ms/字） | F-P0-02 / F-P0-03 / F-P0-04 |
| `ECharts` | 图表渲染（分包异步加载） | F-P1-05 |
| `Skeleton` | 骨架屏加载态 | 全局 |
| `ConfirmDialog` | 确认弹窗 | F-P1-07 / F-P0-08 |
| `ErrorBoundary` | 错误边界 | 全局 |
| `LoadingSpinner` | 加载动画 | 全局 |
| `Toast` | 轻提示 | 全局 |

### 2.6 状态管理

不引入全局状态管理库。状态管理策略：

| 状态类型 | 管理方式 | 示例 |
|----------|----------|------|
| 页面内状态 | React useState / useReducer | 费曼复述输入、考试答题 |
| 跨页面共享状态 | 云数据库 + 本地缓存 | 用户设置、学习记录 |
| 间隔重复计划 | 云数据库 `spaced_repetition` 集合 | 待复习知识点 |
| AI 配置 | `settings` 集合 + 本地缓存 | API Key / Model |

---

## 3. 后端架构（云开发）

### 3.1 云数据库

18 个集合，按用途分类：

#### 静态数据（种子数据，初始化后极少变化）

| 集合 | 数据量 | 来源 |
|------|--------|------|
| `knowledge_nodes` | 800+ | seedKnowledge + extractedKnowledge + extractedKnowledgeNodes |
| `exam_questions` | 36 | seedExamQuestions |
| `causal_chains` | 34 | seedPathways |
| `cases` | 7 | seedCases |

#### 动态数据（用户产生，持续增长）

| 集合 | 用途 | PRD 功能 |
|------|------|----------|
| `learning_records` | 学习记录 | F-P0-06 |
| `feynman_records` | 费曼复述记录 | F-P0-02 |
| `dialogue_records` | 对话记录 | F-P0-03 |
| `case_records` | 病例练习记录 | F-P0-05 |
| `exam_records` | 答题记录 | F-P1-01 |
| `exam_sessions` | 考试会话 | F-P1-01 |
| `wrong_questions` | 错题 | F-P1-01 |
| `spaced_repetition` | 间隔重复计划 | F-P0-06 |
| `study_activities` | 学习活动 | F-P1-05 |
| `favorites` | 收藏 | — |
| `settings` | 用户设置 | F-P0-07 |
| `learning_paths` | 学习路径 | — |
| `study_plans` | 学习计划 | F-P2-04 |
| `study_goals` | 学习目标 | F-P2-04 |

#### 数据安全规则

所有集合的安全规则：读写均以 `openid` 为条件，用户只能访问自己的数据。静态数据集合（knowledge_nodes 等）对所有已登录用户只读。

### 3.2 云函数

| 云函数 | 用途 | PRD 功能 | 调用方 |
|--------|------|----------|--------|
| `initUser` | 微信登录：code → openid | F-P0-07 | 前端 `auth.ts` |
| `initSeedData` | 首次登录种子数据写入 | F-P0-01 | 前端 `seedData.ts` |
| `submitExam` | 考试提交事务（4 表原子写入） | F-P1-01 | 前端 exam 页面 |
| `analytics` | 服务端计算 mastery map / weak points / activity timeline | F-P1-05 | 前端 home 页面 |
| `completePathway` | 推导链完成记录 | F-P1-04 | 前端 pathway 页面 |
| `saveGeneratedContent` | AI 生成内容保存 | F-P2-01 / F-P2-02 | 前端 ai.ts |

**为什么这些逻辑放云函数**：
- `initUser`：需要服务端调用微信 API 换取 openid，客户端无法完成
- `initSeedData`：800+ 条数据分批写入，需服务端执行避免客户端超时
- `submitExam`：4 表原子写入（exam_sessions + exam_records + wrong_questions + study_activities），需事务保证
- `analytics`：需加载全量用户数据计算，客户端加载全表不现实
- `completePathway` / `saveGeneratedContent`：多表写入事务

**不在云函数的逻辑**：
- AI 调用：V1.0 客户端直连（云函数 20s 超时限制）
- 费曼复述评估保存：单表写入，客户端直接操作
- VINDICATE 评估保存：单表写入
- 间隔重复更新：单表更新

---

## 4. 数据模型

### 4.1 核心类型

#### KnowledgeNode

```typescript
interface KnowledgeNode {
  _id: string;
  id: string;
  type: 'concept' | 'mechanism' | 'disease' | 'symptom' | 'treatment' | 'exam';
  title: string;
  subject: string;
  chapter?: string;
  knowledgePath?: string[];
  content: string;
  keyPoints: string[];
  causalLinks: CausalLink[];
  relatedNodes: (string | RelatedNodeRef)[];
  difficulty: 1 | 2 | 3;
  tags: string[];
  source: 'seed' | 'ai-generated';
  sourceReference?: string;
  version?: string;
}
```

#### FeynmanRecord

```typescript
interface FeynmanRecord {
  _id: string;
  openid: string;
  nodeId: string;
  transcript: string;
  aiScore: {
    accuracy: number;
    completeness: number;
    clarity: number;
    depth: number;
  };
  feedback: string;
  createdAt: number;
}
```

#### DialogueRecord

```typescript
interface DialogueRecord {
  _id: string;
  openid: string;
  nodeId: string;
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
  masteryDetected: boolean;
  createdAt: number;
}
```

#### SpacedRepetition

```typescript
interface SpacedRepetition {
  _id: string;
  openid: string;
  nodeId: string;
  nextReview: number;
  interval: number;
  easeFactor: number;
  repetitions: number;
  lastQuality: number;
  updatedAt: number;
}
```

#### ExamSession

```typescript
interface ExamSession {
  _id: string;
  openid: string;
  questionIds: string[];
  score: number;
  weakNodes: string[];
  createdAt: number;
}
```

#### CaseRecord

```typescript
interface CaseRecord {
  _id: string;
  openid: string;
  caseId: string;
  currentStage: number;
  stageScores: Record<string, number>;
  totalScore?: number;
  createdAt: number;
  updatedAt: number;
}
```

### 4.2 AI 评分到 SM-2 映射

费曼复述 AI 评分（0-100）映射为 SM-2 的 quality（0-5）：

| AI 评分 | quality | 含义 |
|---------|---------|------|
| 90-100 | 5 | 完美 |
| 70-89 | 4 | 良好 |
| 50-69 | 3 | 及格 |
| 30-49 | 2 | 困难 |
| 10-29 | 1 | 很差 |
| 0-9 | 0 | 完全不会 |

### 4.3 VINDICATE 统一定义

从 `constants/vindicate.ts` 统一导出（待创建，当前分散在 feynman-detail 和 case-detail 中）：

```typescript
export const VINDICATE_CATEGORIES = [
  { key: 'V', label: '血管性（Vascular）', hint: '血管病变引起的可能...' },
  { key: 'I', label: '感染性（Infectious）', hint: '细菌/病毒/真菌等感染...' },
  { key: 'N', label: '肿瘤性（Neoplastic）', hint: '良性或恶性肿瘤...' },
  { key: 'D', label: '退行性（Degenerative）', hint: '退行性改变...' },
  { key: 'I2', label: '中毒性（Intoxication）', hint: '药物/毒物/代谢产物...' },
  { key: 'C', label: '先天性（Congenital）', hint: '先天发育异常...' },
  { key: 'A', label: '自身免疫（Autoimmune）', hint: '自身免疫反应...' },
  { key: 'T', label: '创伤性（Traumatic）', hint: '物理/机械损伤...' },
  { key: 'E', label: '内分泌（Endocrine）', hint: '激素/代谢紊乱...' },
] as const;
```

> **UI 约束**：`I2` 仅作为内部 key 使用，UI 展示为"中毒性（Intoxication）"，不出现 I2/I² 标记。

---

## 5. 功能-模块映射

### 5.1 P0 功能

| PRD 功能 | 前端页面 | 前端服务/Hook | 后端 |
|----------|----------|---------------|------|
| F-P0-01 知识地图 | `pages/feynman/` | `useStaticData` + `knowledgeGrouping.ts` + `constants/subjects.ts` | 云数据库 `knowledge_nodes` |
| F-P0-02 费曼复述 | `pagesA/feynman-detail/` | `ai.ts: evaluateFeynman` + `useCloudQuery` | 云数据库 `feynman_records` |
| F-P0-03 苏格拉底对话 | `pagesA/feynman-detail/` | `ai.ts: continueLearningDialogue` + `useCloudQuery` | 云数据库 `dialogue_records` |
| F-P0-04 VINDICATE | `pagesA/feynman-detail/` + `pagesA/case-detail/` | `ai.ts: evaluateVindicate` + `constants/vindicate.ts` | 云数据库 `dialogue_records` |
| F-P0-05 病例沙盒 | `pages/clinic-sandbox/` + `pagesA/case-detail/` | `ai.ts: evaluateDiagnosis + evaluateTreatment` | 云数据库 `case_records` + `cases` |
| F-P0-06 间隔重复 | `pages/feynman/` + `pages/home/` | `spacedRepetition.ts` + `useCloudQuery` | 云数据库 `spaced_repetition` |
| F-P0-07 微信登录 | `pages/profile/` + `pagesB/setup/` | `auth.ts` | 云函数 `initUser` + 云数据库 `settings` |
| F-P0-08 合规标识 | 全局（所有 AI 输出区域） | `StreamingContent` 组件内嵌标识 | — |

### 5.2 P1 功能

| PRD 功能 | 前端页面 | 前端服务/Hook | 后端 |
|----------|----------|---------------|------|
| F-P1-01 模拟考试 | `pagesB/exam/` + `pagesB/wrong-questions/` | `useStaticData` + `useCloudQuery` | 云函数 `submitExam` + 云数据库 `exam_sessions/records/wrong_questions` |
| F-P1-02 语音输入 | `pagesA/feynman-detail/` | 微信同声传译插件 + 本地医学术语词典 | — |
| F-P1-03 疾病对比 | `pagesB/compare-mode/` | `ai.ts: extractComparisonDimensions` | 云数据库 `dialogue_records` |
| F-P1-04 推导链 | `pagesA/pathway/` | `useStaticData` | 云函数 `completePathway` |
| F-P1-05 学习仪表盘 | `pages/home/` | `useCloudQuery` + `ECharts` 组件 | 云函数 `analytics` |
| F-P1-06 AI 调用渐进 | `pagesB/settings/` + `services/ai.ts` | V1.0 直连 → V1.5 云函数代理 | V1.5 新增云函数 |
| F-P1-07 账户注销 | `pages/profile/` | `cloud.ts` | 新增云函数 `deleteUserData` |

### 5.3 P2 功能

| PRD 功能 | 前端页面 | 前端服务/Hook | 后端 |
|----------|----------|---------------|------|
| F-P2-01 AI 生成病例 | `pages/clinic-sandbox/` | `ai.ts: generateMedicalCase` | 云函数 `saveGeneratedContent` |
| F-P2-02 AI 生成推导链 | `pagesA/pathway/` | `ai.ts: generateCausalChain` | 云函数 `saveGeneratedContent` |
| F-P2-03 学习日历 | `pagesB/study-calendar/` | `useCloudQuery` | 云数据库 `study_activities` |
| F-P2-04 学习计划 | `pagesB/learning-hub/` | `useCloudQuery` | 云数据库 `study_plans/study_goals` |
| F-P2-05 社交分享 | `pages/profile/` | Canvas 绘制 + `Taro.shareAppMessage` | — |

---

## 6. 核心流程

### 6.1 费曼复述流程（F-P0-02）

```
用户点击知识点
    │
    ▼
feynman-detail 页面（默认费曼模式）
    │
    ▼
展示知识点标题 + AI 提示语
    │
    ▼
用户输入复述文本（文本 / 语音）
    │
    ▼
提交 → ai.ts: evaluateFeynman()
    │
    ├── 0-3s: 展示评估框架骨架（四维度 + 加载动画）
    ├── 3-8s: 逐维度填充评分和反馈
    ├── 15s+: 展示"AI 正在深度分析中" + 取消按钮
    ├── 30s+: 展示超时错误 + 重新提交按钮
    │
    ▼
AI 返回完整评估结果
    │
    ├── 保存至 feynman_records 集合
    ├── 更新 spaced_repetition 集合（SM-2 算法）
    ├── 记录 study_activities
    │
    ▼
展示评估结果 + 后续动作
    ├── "继续对话" → 苏格拉底对话（F-P0-03）
    ├── "查看要点" → 展示 keyPoints 对比
    └── "下次再来" → 返回知识地图
```

### 6.2 VINDICATE 鉴别诊断流程（F-P0-04）

```
用户进入 VINDICATE 模式
    │
    ▼
展示 9 宫格骨架（从 constants/vindicate.ts 读取定义）
    │
    ▼
用户逐类别填写分析文本
    │
    ▼
提交 → ai.ts: evaluateVindicate()
    │
    ├── 0-3s: 展示 9 宫格评估骨架
    ├── 3-8s: 逐类别填充评估结果
    │
    ▼
AI 返回评估结果
    │
    ├── 每类别: correct/incorrect + feedback
    ├── 遗漏类别高亮
    │
    ▼
保存至 dialogue_records 集合
```

### 6.3 病例沙盒流程（F-P0-05）

```
用户选择病例
    │
    ▼
case-detail 页面（6 阶段状态机）
    │
    ├── 阶段1: 主诉分析 → ai.ts: evaluateDiagnosis()
    ├── 阶段2: 现病史采集 → AI 提供病史信息
    ├── 阶段3: 体格检查 → AI 提供查体结果
    ├── 阶段4: 辅助检查 → AI 提供检查结果
    ├── 阶段5: 鉴别诊断 → ai.ts: evaluateVindicate()
    └── 阶段6: 诊疗方案 → ai.ts: evaluateTreatment()
    │
    ▼
每阶段独立评分 → 汇总为病例总分
    │
    ▼
保存至 case_records 集合
支持中途退出并保存进度（currentStage 字段）
```

### 6.4 间隔重复流程（F-P0-06）

```
费曼复述完成 → AI 评分（0-100）
    │
    ▼
映射为 SM-2 quality（0-5）
    │
    ▼
spacedRepetition.ts: 计算 nextReview / interval / easeFactor
    │
    ▼
更新 spaced_repetition 集合
    │
    ▼
知识地图待复习铃铛 🔔 读取 nextReview ≤ 今日的数据
首页"今日待复习"读取同上
```

### 6.5 模拟考试闭环流程（F-P1-01）

```
用户选择范围 + 题量
    │
    ▼
exam 页面（三态状态机：选题 → 答题 → 结果）
    │
    ▼
答题完成 → 云函数 submitExam（4 表原子写入）
    │
    ├── exam_sessions: 考试会话
    ├── exam_records: 每题答题记录
    ├── wrong_questions: 错题
    └── study_activities: 学习活动
    │
    ▼
结果页展示薄弱知识点清单
    │
    ▼
每个错题旁"去费曼复述"按钮
    │
    ▼
点击 → navigateTo feynman-detail（nodeId 参数）
    │
    ▼
进入费曼复述模式 → 完成闭环
```

### 6.6 微信登录流程（F-P0-07）

```
app.tsx onLaunch
    │
    ▼
Taro.login() → 获取 code
    │
    ▼
云函数 initUser(code) → 换取 openid
    │
    ▼
openid 存入全局 + settings 集合
    │
    ▼
检查是否首次登录 → 是 → initSeedData(openid)
```

---

## 7. 分包策略

### 7.1 分包方案

| 包 | 页面 | 体积预算 |
|----|------|----------|
| 主包 | home + feynman + clinic-sandbox + profile + 框架 + 通用组件 + 服务层 | ≤ 1.8MB |
| 分包 pagesA | feynman-detail + case-detail + pathway | ≤ 500KB |
| 分包 pagesB | exam + compare-mode + wrong-questions + settings + study-calendar + learning-hub + setup | ≤ 800KB |
| 分包 echarts | echarts-for-weixin | ≤ 900KB |

### 7.2 体积控制

- ECharts 放入独立分包，主包通过异步加载引用
- 知识地图使用 emoji + CSS 进度环，不使用图片资源
- 种子数据通过云数据库加载，不打包进主包
- 构建后运行 `scripts/check-size.sh` 检查主包体积（阈值 1.8MB）

---

## 8. 技术债务

| 债务 | 影响 | 修复计划 |
|------|------|----------|
| VINDICATE 定义分散在 feynman-detail 和 case-detail 中 | 维护困难，定义不一致 | 创建 `constants/vindicate.ts` 统一导出 |
| AI 调用客户端直连 | API Key 泄露风险 | V1.5 迁移云函数代理 |
| 无 lint/typecheck 配置 | 代码质量无自动保障 | 补充 ESLint + TypeScript 严格模式 |
| 无自动化测试 | 回归风险 | V1.5 补充核心流程测试 |
| 种子数据 3 个源文件合并逻辑复杂 | 维护成本高 | V2.0 统一数据源 |
| ECharts 主包体积风险 | 可能超 2MB 限制 | 验证分包策略 + check-size.sh |

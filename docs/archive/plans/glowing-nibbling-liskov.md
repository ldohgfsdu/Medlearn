# MedLearn → 微信小程序迁移计划

## Context

将 MedLearn Electron 桌面应用（React 19 + Dexie/IndexedDB + 本地 AI 调用 + 32 个 .tsx 文件 + 18 张数据表）迁移为微信小程序，使用 **Taro 4 (React + TypeScript) + 微信云开发（云数据库）**。

核心架构转变：
- **本地优先 → 云端优先 + 本地缓存**
- **桌面三栏布局 → 移动端单栏布局**
- **单用户 → 微信登录多用户**
- **AI 调用保持客户端直连**（不经过云函数代理）

技术选定：Taro (React)、微信云开发（云数据库）、微信登录。

---

## Phase 1: 项目初始化 (2-3 天)

### 1.1 脚手架
- `npx @tarojs/cli init medlearn-miniapp` → React + TypeScript + Webpack5
- 创建目录结构：`pages/`（按页面分目录）、`components/`、`services/`、`hooks/`、`cloud/functions/`
- 配置 `app.config.ts`：定义所有页面路径 + tabBar（4 个主 tab：学习、知识、病例、我的）
- 配置 `subpackages`：种子数据和 ECharts 放分包，减轻主包体积

### 1.2 依赖替换

| 移除 | 新增 |
|------|------|
| react-router-dom | Taro 内置路由 (`@tarojs/taro`) |
| dexie, dexie-react-hooks | 微信云数据库 SDK |
| recharts | echarts（按需引入，不全量 import *）|
| lucide-react | 自定义 SVG 图标组件（仅打包用到的 15 个）|
| tailwindcss, @tailwindcss/vite | SCSS Modules |
| electron, electron-builder | 无（桌面特性全部移除）|

### 1.3 包体积预防措施
- ECharts 按需引入（`import { init } from 'echarts/core'` + 只注册 line/bar/grid/tooltip）
- 种子数据放 `subpackages` 分包
- 图标只打包 15 个实际用到的 SVG
- **Phase 5 结束时跑 `Taro.build` 检查包体积**，别等到 Phase 7

---

## Phase 2: 数据层 (5-6 天) ⭐ 最关键的阶段

### 2.1 云数据库集合设计
18 张 Dexie 表 → 18 个云数据库集合，所有集合自动附带 `_openid` 实现用户隔离：

| 集合名 | 关键索引 |
|--------|---------|
| `knowledge_nodes` | `subject, type, source, version` |
| `causal_chains` | `subject, chapter` |
| `cases` | `subject, difficulty` |
| `exam_questions` | `subject, system, difficulty` |
| `learning_records` | `type, targetId, createdAt` |
| `feynman_records` | `nodeId, createdAt` |
| `case_records` | `caseId, createdAt` |
| `exam_records` | `questionId, createdAt` |
| `exam_sessions` | `subject, startTime` |
| `dialogue_records` | `nodeId, createdAt` |
| `wrong_questions` | `sourceType, subject, isResolved` |
| `favorites` | `itemType, itemId, subject` |
| `study_activities` | `date, activityType, createdAt` |
| `spaced_repetition` | `nodeId, nextReviewDate` |
| `learning_paths` | `subject, isCompleted` |
| `study_plans` | `isActive` |
| `study_goals` | `planId, date, isCompleted` |
| `settings` | `key` |

### 2.2 查询策略（分两类，不搞一刀切）

**策略 A：静态知识数据**（knowledge_nodes, causal_chains, cases, exam_questions）
- 首次加载 → 全量拉取 → 存本地缓存（`wx.setStorageSync`）
- 之后直接从缓存读，**不查云数据库**
- `knowledge_nodes` 集合加 `version` 字段，启动时只查 `version` 变化 → 增量更新
- **不会有页面闪烁**，因为不会先显示旧数据再刷新

**策略 B：动态学习记录**（learning_records, feynman_records, exam_sessions 等）
- 先读本地缓存展示（立即渲染）
- 后台静默查云数据库同步
- **不做乐观更新**：云数据回来之后，如果和缓存一致就不更新 UI，不一致才静默替换缓存（下次打开页面生效）
- 避免用户正在看的时候数据跳动

### 2.3 查询模式替换

| 原模式 | 出现次数 | 新实现 |
|--------|---------|--------|
| `db.table.toArray()` | 15 次 | 静态数据读缓存，动态数据 `useCloudQuery` |
| `db.table.get(id)` | 1 次 | `useCloudQuery({ collectionName, filter: { _id } })` |
| `db.table.where().equals()` | 3 次 | 云数据库 `.where({ field: value }).get()` |
| 多表事务 | 3 处 | 云函数一次性写入 |

### 2.4 云函数：分析计算
`getMasteryMap()`、`getWeakPoints()`、`getActivityTimeline()` 改为云函数服务器端计算，避免加载全表到客户端。

### 2.5 种子数据加载

**不用云函数，改客户端分批写入**：
- 种子数据文件打包进小程序 `src/data/`（原样复制，包括 `taxonomy.json`、`knowledgePath`、`extracted-knowledge.json`）
- 首次登录检测：检查云数据库 `knowledge_nodes` 是否有当前用户的记录
- 数据为空 → 显示进度条 UI → 客户端分批写入云数据库（每批 20 条，避免超时）
- `extracted-knowledge.json`（156KB）如太大，走微信云控制台直接导入（一次性）

### 文件清单
- `src/services/cloud.ts` — 云数据库初始化和操作封装
- `src/services/cache.ts` — 本地缓存读写 + version 比对
- `src/hooks/useCloudQuery.ts` — 动态数据查询 Hook（缓存优先 + 后台同步）
- `src/hooks/useStaticData.ts` — 静态数据 Hook（全量缓存 + version 增量）
- `cloud/functions/analytics/index.js` — 服务器端分析
- `cloud/functions/submitExam/index.js` — 考试提交事务
- `cloud/functions/saveGeneratedContent/index.js` — AI 内容保存
- `cloud/functions/completePathway/index.js` — 推导链完成

---

## Phase 3: 用户认证 (1-2 天)

### 3.1 微信登录流程
```
客户端 wx.login() → 获取 code → 云函数 initUser → code2Session 换取 openid
→ 检查 users 集合 → 新用户则触发种子数据写入 → 返回 userId
```

### 3.2 数据隔离
云数据库自动为每条记录添加 `_openid`，天然实现用户数据隔离。
- API Key、Base URL、模型等 AI 配置存**本地** `wx.setStorageSync`（不存云数据库，避免敏感信息上云）
- 其他业务设置（主题等）存云数据库 `settings` 集合

### 文件清单
- `src/services/auth.ts` — 客户端登录逻辑
- `cloud/functions/initUser/index.js` — 用户初始化云函数

---

## Phase 4: AI 服务 (1 天)

### 4.1 核心决策：客户端直连，不经过云函数

**为什么不用云函数代理**：API Key 作为云函数参数传递会出现在云函数日志中，微信云开发日志可被管理员查看 → 安全漏洞。

**改法**：
```
客户端 (Taro.request) ──直连──→ AI API（DeepSeek / Claude 兼容接口）
                                 ↑
                          用户自己配的 Key + Base URL + Model
```

小程序有 `wx.request` 能力直接调 HTTPS API，不需要代理层。用户 Settings 里配的 API Key 存**本地** `wx.setStorageSync`，调 API 时直接附加。

### 4.2 不做真流式（技术限制）

小程序 `request` 不支持 SSE → 真流式做不了。替代方案：

1. `Taro.request` 调 AI API，`stream: false`
2. 返回完整响应（超时设为 60s，实际通常 5-15 秒返回）
3. 前端打字机效果逐字吐出，**速度 30-50ms/字**（比桌面版快）
4. 加载中显示骨架屏 + "AI 正在思考..."

### 4.3 客户端服务层

`src/services/ai.ts` 重写：
- 保留 9 个 AI 函数签名不变（evaluateFeynman, evaluateVindicate, generateCausalChain 等）
- 每个函数：从 `wx.getStorageSync` 读取 apiKey + baseUrl + model → 通过 `Taro.request` 直连 AI API
- 新增 `fetchModels(baseUrl, apiKey)` → `GET {baseUrl}/v1/models` → 返回模型列表供 Settings 选择器使用
- 新增 `testConnection(baseUrl, apiKey)` → 简单连通性测试

### 4.4 Settings 页面
保留完整 AI 配置表单：
- API Key 输入（password 类型，存本地 `wx.setStorageSync`）
- Base URL 输入（存本地）
- 模型选择器（点击「获取模型列表」从 API 端点拉取，或手动输入）
- 连接测试按钮
- 安全说明提示

### 文件清单
- `src/services/ai.ts` — 重写为 `Taro.request` 直连，无云函数依赖
- `src/pages/settings/index.tsx` — 保留完整 AI 配置表单（本地存储）

---

## Phase 5: UI 框架 (3-4 天)

### 5.1 样式策略
- **SCSS Modules**：每个页面/组件独立 `.module.scss`
- CSS 自定义属性（29 个主题变量）→ SCSS 变量，硬编码值
- **v1 仅浅色主题**，深色模式延后
- 819 处 `style={{}}` 对象：
  - 静态布局样式 → SCSS module 类
  - 动态样式（进度条宽度、数据颜色）→ 保留内联 style

### 5.2 移动端布局重新设计
桌面三栏布局 → 移动端：
- **底部 TabBar**（4 个主 tab：学习、知识、病例、我的）取代左侧 NavRail
- **全屏内容区**取代右侧内容区
- **独立选择页**取代左侧 ListPanel → 点击后 `navigateTo` 进入详情子页面

### 5.3 图标替换
42 个 lucide-react 图标 → 混合策略：
- 常用图标（check, close, arrow, search 等）→ Taro UI 内置图标
- 15 个关键图标（Brain, Sparkles, Stethoscope, AlertTriangle, CheckCircle, BookOpen, FileText, Target, Wand2, Calendar, GraduationCap, FlaskConical, ArrowLeftRight, FolderTree, Loader2）→ 自定义 SVG 组件
- Loader2 → Taro 的 loading 动画

### 5.4 图表替换
Recharts → ECharts（按需引入，只注册 line + bar + grid + tooltip）：
- `DashboardCharts.tsx`（73 行）→ 用 `ec-canvas` 组件 + ECharts option 对象
- LineChart + BarChart 直接映射到 ECharts 的 line + bar 系列

### 5.5 包体积检查点
**Phase 5 结束时必须跑 `Taro.build`**，确认主包 < 2MB。超标措施：
- 种子数据移分包
- ECharts 进一步裁剪
- 图标压缩

### 文件清单
- `src/theme.scss` — 全局 SCSS 变量和混合
- `src/components/icons/*.tsx` — 15 个自定义 SVG 图标
- `src/pages/dashboard/DashboardCharts/index.tsx` — ECharts 版图表

---

## Phase 6: 页面迁移 (5-7 天)

### 迁移顺序（FeynmanRecall 排第一，最难啃的骨头早暴露）

| 优先级 | 页面 | 原文件 | 复杂度 | 关键改动 |
|--------|------|--------|--------|---------|
| **P0** | FeynmanRecall | `FeynmanRecall.tsx` (834行) | 很高 | 3 级分组树→系统 Tab + 可滚动列表，移除 TaxonomyTree，风险最高先做 |
| **P0** | Dashboard | `Dashboard.tsx` (498行) | 高 | 分析计算→云函数，Recharts→ECharts，移动端卡片布局 |
| **P1** | FeynmanDetail | `FeynmanDetail.tsx` | 高 | AI 非流式+打字效果，VINDICATE 面板适配 |
| **P1** | ClinicSandbox | `ClinicSandbox.tsx` (98行) | 中 | 列表+详情合并为移动端导航流 |
| **P1** | CaseDetail | `CaseDetail.tsx` | 高 | 4 阶段诊断流程适配移动端 |
| **P2** | Exam | `Exam.tsx` (291行) | 中 | 提交事务→云函数，列表→活动→结果导航流 |
| **P2** | Pathway | `Pathway.tsx` (359行) | 中 | 步骤器适配移动端 |
| **P2** | Settings | `Settings.tsx` (165行) | 低 | AI 配置存本地存储，新增模型列表动态获取 |
| **P3** | WrongQuestions | `WrongQuestions.tsx` (252行) | 低 | 列表+详情模式 |
| **P3** | StudyCalendar | `StudyCalendar.tsx` (282行) | 低 | 热力图组件替换 |
| **P3** | LearningHub | `LearningHub.tsx` (435行) | 中 | 4 Tab 布局适配 |
| **P3** | CompareMode | `CompareMode.tsx` | 高 | 双疾病选择+11 维对比表格适配 |

### 可保留（直接移植）的部分
- 所有类型定义 (`types/*.ts`)
- 学科目录 (`constants/subjects.ts`)
- 工具函数 (`utils/index.ts`：formatTime, fisherYatesShuffle, toDayKey)
- SM-2 算法 (`utils/spacedRepetition.ts`：计算逻辑不变，DB 操作替换）
- 知识分组逻辑 (FeynmanRecall 中的 System/Chapter/Disease 分组算法)
- 种子数据内容 (`seedKnowledge.ts`, `seedExamQuestions.ts` 等)
- 静态 JSON 数据 (`taxonomy.json`, `knowledgePath` 等 — 原样复制)

### 路由迁移
```typescript
// React Router → Taro
navigate('/feynman/123')   → Taro.navigateTo({ url: '/pages/feynman-detail/index?nodeId=123' })
useParams()                → Taro.useRouter().params
useSearchParams()          → Taro.useRouter().params
```

---

## Phase 7: 测试与发布 (2-3 天)

### 测试清单
- [ ] 微信登录流程端到端
- [ ] 首次登录 → 种子数据分批写入 + 进度条正确
- [ ] 10 个页面全部渲染无错误
- [ ] 静态数据从缓存读取（无闪烁）
- [ ] 动态数据后台同步（不会跳动）
- [ ] AI 直连调用正常（Taro.request）
- [ ] Settings 配置持久化正常
- [ ] 所有写操作正确持久化
- [ ] 页面间导航正常（tabBar + navigateTo）
- [ ] 长列表滚动性能（FeynmanRecall 175+ 条目）
- [ ] 包体积 < 2MB（主包限制）

### 性能优化重点
- 长列表使用 `VirtualList`
- ECharts 按需引入
- 图标总大小 < 50KB
- 种子数据放分包
- 静态数据缓存命中率接近 100%

### 审核准备
- 类目：教育 > 在线教育
- 首次启动展示隐私政策
- AI 生成内容标注
- 无用户生成内容分享功能

---

## 依赖关系

```
Phase 1 (项目初始化)
    │
    ▼
Phase 3 (用户认证)
    │
    ▼
Phase 2 (数据层)  ←── Phase 4 (AI 服务，可与 2 并行)
    │
    ▼
Phase 5 (UI 框架)
    │
    ▼
Phase 6 (页面迁移)
    │
    ▼
Phase 7 (测试与发布)
```

Phase 2 和 Phase 4 可在 Phase 3 完成后并行。

---

## 预估工作量

| 阶段 | 天数 | 复杂度 |
|------|------|--------|
| Phase 1: 项目初始化 | 2-3 | 低 |
| Phase 2: 数据层 | 5-6 | 很高 |
| Phase 3: 用户认证 | 1-2 | 低 |
| Phase 4: AI 服务 | 1 | 低（直连，无云函数）|
| Phase 5: UI 框架 | 3-4 | 高 |
| Phase 6: 页面迁移 | 5-7 | 很高 |
| Phase 7: 测试发布 | 2-3 | 中 |
| **总计** | **20-28 天** | |

单人约 5 周，双人（一人云/数据/AI，一人 UI/页面）约 4 周。

---

## v2 待规划功能
- 深色模式
- 流式 AI 响应（真 SSE，需要小程序插件或 WebSocket）
- TaxonomyTree 导航模式
- 离线支持 + 写入队列
- 间隔重复推送提醒
- 跨设备同步
- AI 出题功能

---

## 参考文件

### 核心迁移源文件
- [src/db/db.ts](src/db/db.ts) — 18 表 Dexie schema（所有表定义 + 索引 → 云数据库集合）
- [src/services/ai.ts](src/services/ai.ts) — 9 个 AI 函数（改为客户端 Taro.request 直连）
- [src/pages/FeynmanRecall.tsx](src/pages/FeynmanRecall.tsx) — 最复杂页面（834 行，P0 第一优先迁移）
- [src/pages/Dashboard.tsx](src/pages/Dashboard.tsx) — 入口页面，分析计算需服务端化
- [src/index.css](src/index.css) — 所有 CSS 自定义属性和布局模式（763 行 → SCSS modules）

### 可保留的文件
- [src/types/](src/types/) — 4 个类型定义文件（直接移植）
- [src/constants/](src/constants/) — 学科目录常量（直接移植）
- [src/utils/index.ts](src/utils/index.ts) — 工具函数（直接移植）
- [src/utils/spacedRepetition.ts](src/utils/spacedRepetition.ts) — SM-2 算法（逻辑保留，DB 替换）
- [src/data/](src/data/) — 静态数据（taxonomy.json, knowledgePath, 种子数据，原样复制进小程序）

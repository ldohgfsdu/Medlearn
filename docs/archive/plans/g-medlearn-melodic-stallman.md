# MedLearn AI 全自动化升级计划

## Context

MedLearn 是一个纯客户端的医学教育 SPA（React 19 + Vite + Dexie/IndexedDB），目前所有 AI 评估都是 mock 逻辑（setTimeout + 关键词匹配），Dashboard/Analytics 的数据全是硬编码的 '0'，学习记录不会保存到 DB，内容仅限 2 条种子因果链和 1 个种子病例。

用户要求全面升级为**AI 驱动**的学习系统：接入 Claude API 做智能评估、自动生成学习路径、自动生成医学内容。

---

## 架构方案

**Claude API 调用方式**：用户自有的兼容 API 代理（`https://api.meai.cloud/`，接口兼容 Anthropic API 格式）。

- 浏览器端直接 fetch 调用（目标服务器支持 CORS，或通过 Vite proxy）
- API Base URL 和 API Key 均存 localStorage，可在设置页修改
- 流式输出使用 SSE（Server-Sent Events）

**API 配置**：
- Base URL: `https://api.meai.cloud`（存 localStorage，可修改）
- API Key: `sk-7G9IMddl5rbBA2O6v6h2BA5wKrp2UdGR8LlPI09as60qXwrV`（用户输入后存 localStorage）
- Model: `claude-opus-4-7`（默认，可在设置页切换）

### 关于 CORS 的处理

由于目标 API 是第三方代理（meai.cloud），不一定支持浏览器 CORS。解决方案：
- 开发环境：Vite proxy 转发
- 生产环境：内嵌一个极简 Express 服务器（`server.js`，约 30 行），仅做 API 转发

---

## 实施步骤

### Phase 1: 基础设施（新建文件为主）

#### 1.1 安装依赖
```bash
cd G:/medlearn && npm install uuid
npm install -D @types/uuid
```

#### 1.2 新建 `src/services/ai.ts` — Claude API 服务层
核心函数：
- `getApiKey()` / `setApiKey()` — localStorage 读写
- `claudeStream(params, onChunk, onDone, onError)` — 基础流式调用
- `evaluateFeynman(node, explanation)` — 费曼评估 prompt
- `evaluateDiagnosis(medicalCase, diagnosis)` — 诊断评估
- `evaluateTreatment(medicalCase, diagnosis, treatment)` — 治疗评估
- `generateCausalChain(subject, topic)` — 生成推导链
- `generateMedicalCase(subject, difficulty)` — 生成病例
- `getLearningRecommendations(records)` — AI 学习建议

流式处理：使用 fetch + ReadableStream 解析 SSE（`data: {"type":"content_block_delta",...}`），通过回调逐块输出。

#### 1.3 更新 `vite.config.ts` — 添加 API 代理
```ts
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api/claude': {
        target: 'https://api.meai.cloud',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/claude/, ''),
      }
    }
  }
})
```
ai.ts 中调用时 base URL 使用 `/api/claude`（开发环境走 proxy，生产环境用内嵌 server.js）。

#### 1.4 新建 `src/pages/Settings.tsx` — 设置页
- API Key 输入（password 类型，可切换显示）
- 保存到 localStorage
- 测试连接按钮（发一条简单消息验证 key 有效）
- 连接状态指示器（✓ 已连接 / ✗ 未连接）
- 路由：`/settings`

#### 1.5 更新 `src/types/knowledge.ts` + `src/types/case.ts` — 添加 source 字段
```ts
// KnowledgeNode, CausalChain, MedicalCase 都加：
source: 'seed' | 'ai-generated';
generatedAt?: number;
```

#### 1.6 更新 `src/db/db.ts` — 升级到 version 2
- 添加 `source` 索引到 knowledgeNodes、causalChains、cases 表
- upgrade 函数：给所有旧记录添加 `source: 'seed'`

---

### Phase 2: 替换 Mock AI 为真实 Claude 调用

#### 2.1 重写 `src/pages/FeynmanRecall.tsx`
- 删除 setTimeout mock（第 20-41 行）
- 新增流式状态：`streamingContent`、`isStreaming`、`accumulatedContent`(useRef)
- `handleSubmit` 调用 `evaluateFeynman(node, explanation)`，流式显示评估过程
- 评估完成后解析结构化 JSON，更新 `evaluation` state
- 保存 `FeynmanRecord` 到 DB
- 未配置 API Key 时提示跳转设置页

#### 2.2 重写 `src/pages/ClinicSandbox.tsx`
- 删除 `handleDiagnosisCheck` 的硬编码字符串匹配（第 27-33 行）
- 删除 `handleTreatmentCheck` 的硬编码匹配（第 36-44 行）
- 新增 `diagnosisEvaluation` / `treatmentEvaluation` state
- 诊断和治疗提交后调用 Claude API 流式评估
- 完成时保存 `CaseRecord` 到 DB

---

### Phase 3: 学习记录持久化

#### 3.1 更新 `src/pages/Pathway.tsx`
- 记录开始时间（useRef）、每步答题结果（useState）
- 完成后保存 `LearningRecord` 到 DB（type: 'pathway'）
- 完成页面显示统计摘要（正确率、用时）

#### 3.2 更新 `src/pages/ClinicSandbox.tsx`（配合 Phase 2.2）
- 记录每个阶段的进入时间
- 保存 `CaseRecord`（包含 diagnosis、treatment 的 AI 评估结果）

---

### Phase 4: Dashboard & Analytics 真实数据

#### 4.1 新建 `src/services/analytics.ts` — 分析计算层
- `getDashboardStats()` — 从 DB 计算 4 项统计
- `getMasteryMap()` — 每个知识点的掌握度（基于 Feynman 分数 + Pathway 正确率）
- `getWeakPoints()` — 从错误记录中提取薄弱环节
- `getActivityTimeline(days)` — 每日学习时长/正确率时间线
- `generateRecommendations()` — 基于未完成内容 + 薄弱环节生成推荐

掌握度算法：
- 完成该节点的 pathway → +20%
- Feynman 分数 >80 → +30%
- 正确诊断/治疗相关病例 → +25%
- 上限 100%，7 天未复习衰减 10%

#### 4.2 重写 `src/pages/Dashboard.tsx`
- 用 `useLiveQuery` 查询所有记录表
- 用 `useMemo` 计算真实统计值
- 新增「AI 推荐学习」区域：基于 analytics 服务生成 2-3 个推荐卡片
- 显示「继续上次学习」快捷入口

#### 4.3 重写 `src/pages/Analytics.tsx`
- 用 Recharts（已安装）绘制真实图表：
  - 知识点掌握度柱状图（X: 知识点名, Y: 掌握%）
  - 学习时间趋势折线图（X: 日期, Y: 分钟）
- 真实薄弱环节列表（可点击跳转复习）
- 日期范围筛选（7天/30天/全部）

---

### Phase 5: AI 内容自动生成

#### 5.1 新建 `src/components/ai/ContentGenerator.tsx` — 内容生成器
- 两种模式：「生成推导链」和「生成病例」
- 输入表单：学科（下拉）、主题（文本）、难度（1-3）
- 流式显示生成过程
- 生成完成后预览 → 确认保存到 IndexedDB
- 保存时标记 `source: 'ai-generated'`

#### 5.2 更新 `src/pages/KnowledgeMap.tsx`
- 添加「AI 生成」标签页/筛选
- 添加「生成新内容」按钮（打开 ContentGenerator）
- 内容卡片显示 source 标识（seed vs AI 生成）
- AI 生成内容可删除

#### 5.3 `src/services/ai.ts` 添加生成函数
Prompt 设计要点：
- **推导链生成**：要求返回 JSON，包含 title/description/steps[]（每步含 question/options/explanation），选项格式与 ChainStep 一致
- **病例生成**：要求返回 JSON，结构与 MedicalCase 类型完全匹配
- 所有 prompt 要求中文输出，医学专业水平，难度匹配

---

### Phase 6: 路由 & UI 整合

#### 6.1 更新 `src/App.tsx`
- 添加 Settings 路由

#### 6.2 更新 `src/components/layout/Sidebar.tsx`
- 添加「设置」导航项（齿轮图标）
- 添加「AI 生成」快捷入口
- API Key 状态指示灯（绿色=已配置, 红色=未配置）

---

## 关键文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/services/ai.ts` | **新建** | Claude API 服务层，流式调用 |
| `src/services/analytics.ts` | **新建** | 学习数据分析计算 |
| `src/pages/Settings.tsx` | **新建** | API Key 配置页 |
| `src/components/ai/ContentGenerator.tsx` | **新建** | AI 内容生成器组件 |
| `vite.config.ts` | 修改 | 添加 API 代理 |
| `src/types/knowledge.ts` | 修改 | 添加 source 字段 |
| `src/types/case.ts` | 修改 | 添加 source 字段 |
| `src/db/db.ts` | 修改 | 升级 schema v2 |
| `src/App.tsx` | 修改 | 添加 Settings 路由 |
| `src/components/layout/Sidebar.tsx` | 修改 | 添加导航项 |
| `src/pages/FeynmanRecall.tsx` | 重写核心逻辑 | 替换 mock → Claude API |
| `src/pages/ClinicSandbox.tsx` | 重写核心逻辑 | 替换 mock → Claude API + 保存记录 |
| `src/pages/Pathway.tsx` | 修改 | 完成时保存 LearningRecord |
| `src/pages/Dashboard.tsx` | 重写 | 真实统计 + AI 推荐 |
| `src/pages/Analytics.tsx` | 重写 | 真实图表 + 薄弱环节 |
| `src/pages/KnowledgeMap.tsx` | 修改 | 添加生成入口 + source 筛选 |
| `src/db/seedKnowledge.ts` | 修改 | 给种子数据添加 source: 'seed' |

---

## 验证方案

1. **Settings 页**：输入 API Key → 测试连接 → 显示成功
2. **Feynman 评估**：选择知识点 → 输入解释 → 看到流式 AI 评估 → 保存到 DB
3. **病例模拟**：完成诊断/治疗 → AI 流式反馈 → CaseRecord 保存
4. **Pathway**：完成推导链 → LearningRecord 保存 → Dashboard 统计更新
5. **Dashboard**：显示真实统计值 + AI 推荐卡片
6. **Analytics**：图表显示真实数据
7. **内容生成**：输入主题 → AI 生成推导链/病例 → 预览 → 保存 → KnowledgeMap 中可见
8. **整体流程**：启动 `npm run dev` → 使用所有功能 → 检查 IndexedDB 中数据完整性

# MedLearn PRD 实现计划

## Context

当前代码库已完成 Expo 迁移，有 3 个页面（首页、知识地图、费曼复述），Supabase 后端含 16 张表。PRD 描述了一个完整的 AI 临床推理训练平台，包含 Case Simulator、Socratic Tutor、VINDICATE Trainer、评分引擎、游戏化等模块。需要按 PRD 逐步实现。

## 实现策略：分阶段推进

### Phase 1：基础架构 + Case Simulator MVP（核心）

PRD 的北极星是 Case Simulator，这是产品核心。Phase 1 聚焦让一个病例从头到尾跑通。

#### 1.1 设计系统 & 主题

**文件**: `constants/theme.ts`, `constants/colors.ts`

按 PRD 第 23-28 章建立设计 token：
- 颜色系统（Primary #6366F1、语义色、中性色、掌握度色）
- 字体系统（Inter + Noto Sans SC）
- 间距系统（4px 网格）
- 圆角、阴影规范
- 组件样式常量

#### 1.2 5-Tab 导航重构

**文件**: `app/_layout.tsx`, 新增 `app/(tabs)/` 路由组

PRD 要求底部 5-Tab：首页、病例中心、学习、分析、个人中心

```
app/
├── _layout.tsx              # Root layout (AuthProvider + QueryClientProvider)
├── (auth)/
│   ├── login.tsx            # 登录页
│   └── register.tsx         # 注册页
├── (tabs)/
│   ├── _layout.tsx          # 5-Tab 导航
│   ├── index.tsx            # 首页（重构）
│   ├── cases.tsx            # 病例中心
│   ├── learn.tsx            # 学习（Tutor Hub）
│   ├── analytics.tsx        # 分析（Phase 1 简化版）
│   └── profile.tsx          # 个人中心
├── case/
│   ├── [sessionId]/
│   │   ├── chat.tsx         # 病例对话页
│   │   ├── diagnose.tsx     # 诊断提交页
│   │   ├── treat.tsx        # 治疗提交页
│   │   └── score.tsx        # 评分报告页
├── feynman.tsx              # 费曼复述（已有，保留）
└── map.tsx                  # 知识地图（已有，保留）
```

#### 1.3 认证系统

**文件**: `app/(auth)/login.tsx`, `app/(auth)/register.tsx`, `hooks/useAuth.ts`

- Supabase Auth 登录/注册 UI
- AuthProvider 包裹全局
- 未登录跳转登录页
- 用户 profile 自动创建（已有 trigger）

#### 1.4 Case Simulator 数据库扩展

**文件**: `supabase/migrations/003_case_simulator.sql`

扩展现有 `cases` 表结构，新增：
- `case_sessions` 表（病例会话状态，含 phase、revealed、conversation JSONB）
- `case_messages` 表（对话消息）
- `case_scores` 表（评分记录）

同时需要按 PRD 第 65 章三层数据架构设计病例模板数据格式。

#### 1.5 病例中心页面

**文件**: `app/(tabs)/cases.tsx`

- 按主诉分类展示（胸痛、呼吸困难、腹痛、发热、意识改变）
- 每个主诉下显示可用病例数和难度
- 已完成病例列表（含分数）
- 点击进入病例对话

#### 1.6 病例对话引擎

**文件**: `services/case-engine.ts`, `services/intent-parser.ts`, `services/patient-renderer.ts`

按 PRD 第 66-69 章实现：

- **Intent Parser**: 规则匹配（82%）+ LLM fallback（18%），识别用户意图（问病史/查体/开检查/提交诊断等）
- **Patient Renderer**: 基于 Ground Truth 用 LLM 渲染患者对话
- **State Machine**: 管理病例阶段（INTRO → HISTORY → EXAM → TESTS → DIAGNOSIS → TREATMENT → SCORING → FEEDBACK）
- **信息释放**: 用户通过交互逐步解锁 Patient World 数据

#### 1.7 病例对话 UI

**文件**: `app/case/[sessionId]/chat.tsx`, `components/case/`

按 PRD 第 29.3 章线框图：
- 顶部：返回 + 患者信息 + 计时器
- 中部：Phase 指示器（问诊→查体→检查→诊断→治疗）
- 消息列表：患者气泡（左侧）+ 医生气泡（右侧）
- 底部：快捷操作栏（查体、开检查）+ 输入框 + 发送按钮
- 查体/检查用 Bottom Sheet 展示

#### 1.8 评分引擎

**文件**: `services/scoring-engine.ts`

按 PRD 第 12 章和第 64.4 章实现四维度评分：
- 诊断准确性 40%（精确匹配/同义词/部分匹配/分类匹配）
- 鉴别诊断 20%
- 证据运用 20%
- 治疗方案 20%（含危险措施惩罚）

#### 1.9 诊断提交 & 评分报告 UI

**文件**: `app/case/[sessionId]/diagnose.tsx`, `app/case/[sessionId]/score.tsx`, `components/score/`

- 诊断提交页：主诊断输入 + 鉴别诊断列表 + 诊断依据（按 PRD 29.4）
- 评分报告页：总分环 + 四维度进度条 + 详细分析 + 学习建议（按 PRD 29.5）

---

### Phase 2：Tutor 模块 + 首页重构

#### 2.1 Feynman Tutor 增强

改造现有 `app/feynman.tsx`，按 PRD 第 8 章：
- 多轮对话（AI 追问机制）
- 知识漏洞报告（理解得分 + 各知识点状态）
- 边界处理（输入太短、说不知道、跑题等）

#### 2.2 Socratic Tutor

新增 `app/socratic.tsx`，按 PRD 第 9 章：
- 苏格拉底式提问（假设检验→鉴别诊断→检查策略→决策推理→治疗推理）
- 五层评分维度

#### 2.3 VINDICATE Trainer

新增 `app/vindicate.tsx`，按 PRD 第 10 章：
- 9 类鉴别诊断训练
- 覆盖率评分

#### 2.4 首页重构

改造 `app/(tabs)/index.tsx`，按 PRD 第 6 章：
- 个性化问候 + Streak
- 今日目标进度条
- 推理分数 / 知识分数
- 继续学习卡片
- AI 推荐横滑卡片
- 待复习提醒

#### 2.5 学习页面（Tutor Hub）

新增 `app/(tabs)/learn.tsx`，按 PRD 第 7 章：
- Tutor 卡片网格（Feynman、Socratic、VINDICATE、诊断训练）
- 每个卡片显示训练目标、难度、时长

---

### Phase 3：游戏化 + 分析 + 个人中心

#### 3.1 游戏化系统

**文件**: `services/gamification.ts`, `hooks/useGamification.ts`

按 PRD 第 15 章：
- XP 系统（病例+100、Feynman+30 等）
- 等级系统（医学生→Intern→Resident→...）
- 成就勋章
- Streak 连续学习天数

#### 3.2 分析仪表盘

**文件**: `app/(tabs)/analytics.tsx`

Phase 1 简化版：
- 知识维度（各系统掌握度）
- 推理维度（诊断准确率趋势）
- 学习时长统计

#### 3.3 个人中心

**文件**: `app/(tabs)/profile.tsx`

- 用户信息展示
- 成就/等级
- 学习设置
- 退出登录

---

### Phase 4：记忆系统 + 搜索 + 完善

#### 4.1 记忆系统（基于已有 spaced_repetition 表）

- SM-2 算法实现
- 复习卡片 UI
- 每日复习提醒

#### 4.2 搜索系统

- 知识点搜索
- 病例搜索

#### 4.3 通知系统

- 每日学习提醒
- 复习提醒

---

## 当前实施：Phase 1 详细步骤

### Step 1: 设计系统常量

创建 `constants/theme.ts`：
- 颜色 token（primary、semantic、neutral、mastery）
- 字体 token
- 间距 token
- 圆角/阴影 token

### Step 2: 认证系统

1. 创建 `hooks/useAuth.ts`（Supabase Auth hook）
2. 创建 `app/(auth)/login.tsx`
3. 创建 `app/(auth)/register.tsx`
4. 修改 `_layout.tsx` 包裹 AuthProvider

### Step 3: 5-Tab 导航

1. 创建 `app/(tabs)/_layout.tsx`
2. 迁移 index → `app/(tabs)/index.tsx`
3. 创建 `app/(tabs)/cases.tsx`（占位）
4. 创建 `app/(tabs)/learn.tsx`（占位）
5. 创建 `app/(tabs)/analytics.tsx`（占位）
6. 创建 `app/(tabs)/profile.tsx`（占位）
7. 移动 map.tsx、feynman.tsx 到合适位置

### Step 4: Case Simulator 数据库

1. 创建 `supabase/migrations/003_case_simulator.sql`
2. 设计 case_sessions、case_messages 表
3. 设计病例模板 JSONB 结构

### Step 5: 病例种子数据

1. 创建 1-2 个胸痛病例模板（JSON）
2. 含完整 Ground Truth + Patient World + Scoring Rubric

### Step 6: Intent Parser

1. 创建 `services/intent-parser.ts`
2. 规则库（问病史、查体、开检查等模式匹配）

### Step 7: Case Engine 核心

1. 创建 `services/case-engine.ts`
2. State Machine（阶段管理）
3. Patient Renderer（LLM 渲染患者对话）
4. 信息释放逻辑

### Step 8: 病例对话 UI

1. 创建 `app/case/[sessionId]/chat.tsx`
2. 创建 `components/case/ChatBubble.tsx`
3. 创建 `components/case/PhaseIndicator.tsx`
4. 创建 `components/case/ChatInput.tsx`
5. 创建 `components/case/QuickActionBar.tsx`
6. 创建 `components/case/ExamSheet.tsx`（查体 Bottom Sheet）
7. 创建 `components/case/TestOrderSheet.tsx`（检查 Bottom Sheet）

### Step 9: 评分引擎

1. 创建 `services/scoring-engine.ts`
2. 四维度评分逻辑

### Step 10: 诊断 & 评分 UI

1. 创建 `app/case/[sessionId]/diagnose.tsx`
2. 创建 `app/case/[sessionId]/score.tsx`
3. 创建 `components/score/ScoreRing.tsx`
4. 创建 `components/score/DimensionBar.tsx`

---

## 验证方式

1. `npx expo start` 启动无报错
2. 5-Tab 导航正常切换
3. 登录/注册流程走通
4. 选择病例 → 对话 → 查体 → 开检查 → 提交诊断 → 查看评分，全流程跑通
5. AI 对话不泄露诊断信息
6. 评分结果合理

## 关键文件清单

**新建文件**:
- `constants/theme.ts`
- `hooks/useAuth.ts`
- `app/(auth)/login.tsx`
- `app/(auth)/register.tsx`
- `app/(tabs)/_layout.tsx`
- `app/(tabs)/cases.tsx`
- `app/(tabs)/learn.tsx`
- `app/(tabs)/analytics.tsx`
- `app/(tabs)/profile.tsx`
- `app/case/[sessionId]/chat.tsx`
- `app/case/[sessionId]/diagnose.tsx`
- `app/case/[sessionId]/treat.tsx`
- `app/case/[sessionId]/score.tsx`
- `services/case-engine.ts`
- `services/intent-parser.ts`
- `services/patient-renderer.ts`
- `services/scoring-engine.ts`
- `services/gamification.ts`
- `components/case/*.tsx`
- `components/score/*.tsx`
- `supabase/migrations/003_case_simulator.sql`

**修改文件**:
- `app/_layout.tsx` → AuthProvider 包裹
- `app/index.tsx` → 移动到 `app/(tabs)/index.tsx` 并重构
- `app/feynman.tsx` → 保留，后续增强
- `app/map.tsx` → 保留

> [!WARNING]
> Archived documentation index from 2026-06-04. Links, feature status and technical claims below are historical.

# Medlearn 项目文档

**项目名称**：Medlearn - AI 驱动的医学思维训练移动应用
**文档版本**：1.1
**最后更新**：2026-06-04

---

## 项目简介

Medlearn 是一款 AI 驱动的医学思维训练移动应用（Android APK），帮助医学生和规培医生通过**费曼学习法**和 **VINDICATE 鉴别诊断框架**建立系统化临床思维，而非死记硬背。

### 核心理念

> **致广大而尽精微，极高明而道中庸**

### 核心价值

> **教用户"怎么想"，不是"记什么"。**

---

## 文档目录

### 1. 产品文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **MVP 执行 PRD** | Phase 1 范围、指标、风险、医学审核与发布门槛 | [MVP_PRD.md](./MVP_PRD.md) |
| **需求文档（PRD）** | 产品需求、功能规划、用户画像、优先级排序 | [PRD.md](./PRD.md) |

### 2. 技术文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **技术架构文档** | 前后端架构、数据模型、分包策略 | [TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md) |
| **后端接口文档** | Supabase 接口、AI 服务接口 | [API.md](./API.md) |

### 3. 工具文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **PDF 提取方案** | 教材 PDF 提取流程、脚本使用指南 | [PDF_EXTRACTION_GUIDE.md](./PDF_EXTRACTION_GUIDE.md) |

---

## 功能规划

### P0 核心功能（V1.0）

| 功能 | 说明 | 状态 |
|------|------|------|
| 知识地图 | 三明治结构展示 800+ 知识点 | ✅ 已完成 |
| 费曼复述 | AI 四维度评估（准确性/完整性/清晰度/深度） | ✅ 已完成 |
| 苏格拉底对话 | AI 引导式提问，深化理解 | ✅ 已完成 |
| VINDICATE 鉴别诊断 | 九维度系统分析框架 | ✅ 已完成 |
| 病例沙盒 | 6 阶段临床模拟训练 | ✅ 已完成 |
| 间隔重复 | SM-2 算法动态调整复习计划 | ✅ 已完成 |
| 用户认证 | Supabase Auth（邮箱/密码 + 匿名登录） | ✅ 已完成 |
| 医学内容合规 | AI 输出标识、免责声明 | ✅ 已完成 |

### P1 增强功能（V1.5）

| 功能 | 说明 | 状态 |
|------|------|------|
| 模拟考试 | 与费曼复述打通的学习闭环 | 🔄 开发中 |
| 语音输入 | Web Speech API 或第三方语音识别 | 📋 计划中 |
| 疾病对比 | AI 多维度对比分析 | 📋 计划中 |
| 推导链 | 4-6 步临床推理训练 | 📋 计划中 |
| 学习仪表盘 | 学习数据可视化 | 📋 计划中 |

### P2 扩展功能（V2.0）

| 功能 | 说明 | 状态 |
|------|------|------|
| AI 生成病例 | 根据薄弱点动态生成 | 📋 计划中 |
| AI 生成推导链 | 动态生成推理链 | 📋 计划中 |
| 学习日历 | 日历视图展示学习活动 | 📋 计划中 |
| 学习计划 | 个性化学习目标 | 📋 计划中 |
| 社交分享 | 学习成果分享 | 📋 计划中 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | Expo 56 + React Native 0.79 + TypeScript |
| 路由 | Expo Router（文件系统路由） |
| 状态管理 | @tanstack/react-query |
| 后端 | Supabase (PostgreSQL + Auth + Storage + pgvector) |
| AI | mimo-v2.5-pro（OpenAI 兼容接口） |
| 向量检索 | Supabase pgvector (BGE-M3 384维) |
| 构建 | EAS Build (Android / iOS) |

---

## 项目结构

```
Medlearn/
├── app/                           # Expo Router 页面
│   ├── _layout.tsx                # 根布局 (AuthProvider + QueryClient)
│   ├── (auth)/                    # 认证路由组
│   │   ├── login.tsx
│   │   └── register.tsx
│   ├── (tabs)/                    # Tab 导航
│   │   ├── index.tsx              # 首页
│   │   ├── cases.tsx              # 病例中心
│   │   ├── learn.tsx              # 学习
│   │   ├── analytics.tsx          # 分析
│   │   └── profile.tsx            # 个人中心
│   ├── case/[sessionId]/          # 病例模拟
│   │   ├── chat.tsx               # 对话页
│   │   ├── diagnose.tsx           # 诊断提交
│   │   ├── treat.tsx              # 治疗方案
│   │   └── score.tsx              # 评分报告
│   ├── map.tsx                    # 知识地图
│   └── feynman.tsx                # 费曼复述
│
├── constants/                     # 常量定义
│   ├── theme.ts                   # 设计系统 (颜色/字体/间距)
│   └── vindicate.ts               # VINDICATE 框架 + 病例枚举
│
├── services/                      # 服务层
│   ├── ai.ts                      # AI 调用 (RAG + 患者对话)
│   ├── case-engine.ts             # 病例引擎 (状态机 + 信息释放)
│   ├── intent-parser.ts           # 意图解析 (规则 82% + LLM 18%)
│   ├── scoring-engine.ts          # 四维度评分引擎
│   ├── analytics.ts               # 事件追踪
│   └── vector.ts                  # 向量嵌入服务
│
├── hooks/                         # React Query Hooks
│   ├── useAuth.tsx                # 认证 Hook + AuthProvider
│   └── useKnowledge.ts            # 知识点查询
│
├── lib/                           # 工具库
│   └── supabase.ts                # Supabase 客户端
│
├── supabase/                      # Supabase 配置
│   ├── migrations/                # 数据库迁移
│   └── seeds/                     # 种子数据
│
├── scripts/                       # 数据管道
│   ├── ingest_textbook.py         # PDF 提取
│   └── ingest_with_tree.py        # 树形结构提取
│
└── docs/                          # 项目文档
    ├── README.md                  # 本文件
    ├── MVP_PRD.md                 # MVP 执行 PRD
    └── PRD.md                     # 完整 PRD
```

---

## 快速开始

### 1. 开发运行

```bash
npm install
npx expo start --web       # Web 预览
npx expo start --android   # Android 预览
```

### 2. 数据库迁移

在 Supabase Dashboard 的 SQL Editor 中按顺序执行：
1. `supabase/migrations/001_initial_schema.sql`
2. `supabase/migrations/002_enable_pgvector.sql`
3. `supabase/migrations/003_case_simulator.sql`
4. `supabase/migrations/004_medical_issue_reports.sql`
5. `supabase/migrations/005_case_events.sql`
6. `supabase/seeds/001_chest_pain_cases.sql`（种子数据）

### 3. 环境变量

复制 `.env.example` 为 `.env`，填入 Supabase 和 AI API 密钥。

---

## 相关资源

- **Expo 文档**：https://docs.expo.dev
- **Expo Router**：https://docs.expo.dev/router
- **Supabase 文档**：https://supabase.com/docs
- **VINDICATE 框架**：临床医学教学方法论，鉴别诊断分类系统
- **费曼学习法**：Richard Feynman 提出的学习方法

---

## 联系方式

如有问题或建议，请联系开发团队。

---

*文档结束。本文档为 Medlearn 项目的总览文档，详细内容请查看各子文档。*

# MedLearn

AI 驱动的医学思维训练移动应用，帮助医学生和规培医生通过费曼学习法和 VINDICATE 鉴别诊断框架建立系统化临床思维，而非死记硬背。

> **核心理念**: 致广大而尽精微，极高明而道中庸

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Expo + React Native + TypeScript | 一份代码，Android + iOS 双端 |
| 路由 | Expo Router | 文件系统路由 |
| 后端 | Supabase | PostgreSQL + Auth + Storage |
| 向量检索 | pgvector | RAG 语义搜索 |
| AI | mimo-v2.5-pro | 费曼复述评估 |
| 数据管线 | Python (PyMuPDF + sentence-transformers) | 教材 PDF 向量化入库 |

## 核心功能

- **费曼复述** - AI 评分和反馈，检验知识掌握程度
- **苏格拉底对话** - 追问式学习，深入理解机制
- **病例沙盒** - 渐进式病例分析，培养临床思维
- **推导链** - VINDICATE 框架训练，建立鉴别诊断能力
- **模拟考试** - 薄弱知识点诊断，精准查漏补缺
- **间隔重复** - SM-2 算法，科学记忆巩固

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入 Supabase 和 AI API 的凭据。

### 3. 初始化数据库

在 Supabase Dashboard 的 SQL Editor 中按顺序执行：

1. `supabase/migrations/001_initial_schema.sql` — 创建 16 张表、RLS 策略、触发器
2. `supabase/migrations/002_enable_pgvector.sql` — 启用向量搜索
3. `supabase/init_database.sql` — 插入测试种子数据
4. `supabase/grant_permissions.sql` — 设置权限

### 4. 启动开发服务器

```bash
npx expo start
```

- 手机安装 **Expo Go** App，扫码即可预览
- 按 `a` 在 Android 模拟器打开
- 按 `i` 在 iOS 模拟器打开

### 5. 构建 APK / IPA

```bash
# Android
npx eas build --platform android

# iOS（需要 Apple Developer 账号）
npx eas build --platform ios
```

## 项目结构

```
├── app/                    # Expo Router 页面
│   ├── _layout.tsx         # 根布局（Tab Navigator）
│   ├── index.tsx           # 首页（学习仪表盘）
│   ├── map.tsx             # 知识地图
│   └── feynman.tsx         # 费曼复述
├── lib/
│   └── supabase.ts         # Supabase 客户端 + 向量搜索
├── services/
│   ├── ai.ts               # RAG 评估引擎
│   └── vector.ts           # Embedding 服务
├── hooks/
│   └── useKnowledge.ts     # React Query hooks
├── utils/
│   └── graph.ts            # 知识图谱工具
├── supabase/               # 数据库 schema 和迁移脚本
├── scripts/                # Python 数据管线（教材 PDF 入库）
├── docs/                   # 产品文档（PRD、API、架构）
└── assets/                 # 图标、启动图
```

## 数据库架构

- **静态数据**: `knowledge_nodes`、`exam_questions`、`causal_chains`、`cases`
- **用户数据**: `user_profiles`、`feynman_records`、`exam_records` 等（RLS 保护）
- **向量检索**: `document_chunks`（pgvector，支持语义搜索）

## 教材数据入库

```bash
cd scripts
pip install -r requirements.txt
python check_env.py
python ingest_with_tree.py
```

详见 [PDF 提取指南](docs/PDF_EXTRACTION_GUIDE.md)。

## 许可证

MIT

# MedLearn 迁移计划：Taro → Expo (React Native)

## Context

当前项目使用 Taro 4 + Capacitor 打包 Android APK，这条链路绕且性能差。用户决定迁移到 Expo (React Native)，实现一份代码同时出 Android + iOS。需要删除旧的 Taro 项目文件，搭建新的 Expo 骨架，迁移可复用代码，并更新 README。

## 要保留的文件（不动）

- `.env`、`.env.example`、`.gitignore`、`agent.md`
- `supabase/` — 整个目录（数据库 schema 和迁移脚本）
- `scripts/` — 整个目录（Python 数据管线）
- `docs/` — 整个目录（PRD、API 文档等）
- `.idea/`、`.swc/` — IDE 配置（gitignore 的）

## 要删除的文件

### 根目录 Taro/旧配置
- `babel.config.js`
- `capacitor.config.ts`
- `package.json`（会被 Expo 的替代）
- `package-lock.json`
- `tsconfig.json`（会被 Expo 的替代）
- `SETUP.md`（需要重写）

### config/ 目录（Taro 构建配置）
- `config/index.ts`
- `config/dev.ts`
- `config/prod.ts`

### src/ 目录（全部删除，用 Expo 重写）
- `src/app.config.ts`、`src/app.tsx`、`src/app.scss`、`src/index.html`
- `src/pages/` — 所有页面（Taro 组件，需用 RN 重写）
- `src/hooks/useKnowledge.ts` — 逻辑可迁移，但查询字段需适配 RN
- `src/lib/supabase.ts` — 逻辑可迁移
- `src/lib/supabase/client.ts`、`src/lib/supabase/types.ts`
- `src/services/` — 所有服务（逻辑可迁移）
- `src/utils/graph.ts` — 纯逻辑可迁移

### android/ 目录
- `android/` — Capacitor 生成的，Expo 会重新生成

### dist/ 目录
- `dist/` — Taro 构建产物

## 新建 Expo 项目

在 `g:\ml` 目录下用 `create-expo-app` 初始化，然后手动迁移可复用代码。

### 新项目结构
```
g:\ml\
├── app/                    # Expo Router 页面
│   ├── _layout.tsx         # 根布局（Tab Navigator）
│   ├── index.tsx           # 首页（学习仪表盘）
│   ├── map.tsx             # 知识地图
│   └── feynman.tsx         # 费曼复述
├── lib/
│   └── supabase.ts         # Supabase 客户端 + 向量搜索（从旧代码迁移）
├── services/
│   ├── ai.ts               # RAG 评估引擎（从旧代码迁移，去掉硬编码 key）
│   └── vector.ts           # Embedding 服务（从旧代码迁移）
├── hooks/
│   └── useKnowledge.ts     # React Query hooks（从旧代码迁移）
├── utils/
│   └── graph.ts            # 知识图谱工具（从旧代码迁移）
├── assets/                 # 图标、字体
├── app.json                # Expo 配置
├── tsconfig.json           # TypeScript 配置
├── package.json            # 依赖
├── .env.example            # 环境变量模板
├── .env                    # 环境变量（gitignore）
├── supabase/               # ← 保留
├── scripts/                # ← 保留
├── docs/                   # ← 保留
├── agent.md                # ← 保留
└── README.md               # ← 更新
```

### 依赖
- `expo` ~52
- `expo-router` — 文件系统路由
- `react-native` / `react`
- `@supabase/supabase-js`
- `@tanstack/react-query`
- `react-native-url-polyfill`（Supabase 在 RN 中需要）
- `@expo/vector-icons`（替代 lucide-react）

## 执行步骤

1. **删除旧文件** — 删掉 config/、src/、android/、dist/、根目录 Taro 配置文件
2. **创建 Expo 项目** — 在 g:\ml 下运行 `npx create-expo-app@latest . --template blank-typescript`（在当前目录初始化）
3. **配置 Expo Router** — 安装 expo-router，配置 app.json 和 _layout.tsx
4. **迁移业务代码** — 把 lib/supabase.ts、services/、hooks/、utils/ 的逻辑迁移过来，适配 RN 环境
5. **创建页面** — 用 React Native 组件重写首页、知识地图、费曼复述三个页面
6. **更新 README** — 反映新的技术栈和项目结构
7. **更新 .gitignore** — 添加 Expo 相关的忽略规则
8. **清理 git** — `git rm` 已删除的旧文件，提交新代码

## README 更新内容

- 技术栈改为 Expo + React Native + TypeScript
- 移除 Capacitor 相关说明
- 添加 iOS 构建说明
- 更新快速启动步骤（`npx expo start`）
- 更新项目结构图
- 保留数据库架构和数据管线说明

## 验证方式

1. `npx expo start` 能启动开发服务器
2. Expo Go 扫码能在手机上看到首页
3. Supabase 连接正常（环境变量配置后）
4. `git status` 干净，旧文件已清理

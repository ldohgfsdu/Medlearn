# MedLearn 项目配置指南

## 技术栈（已更新）

| 层 | 技术 | 说明 |
|----|------|------|
| **前端框架** | Taro 4 + React 18 | 编译为 H5（网页应用） |
| **打包方式** | Capacitor | 将 H5 打包为 Android APK |
| **后端服务** | Supabase | 免费额度：500MB 数据库、1GB 存储 |
| **数据库** | PostgreSQL (Supabase) | 替代微信云数据库 |
| **认证** | Supabase Auth | 替代微信登录 |

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 配置 Supabase

1. 访问 [Supabase](https://supabase.com) 注册账号
2. 创建新项目
3. 获取项目 URL 和 Anon Key
4. 复制 `.env.example` 为 `.env` 并填入配置

```bash
cp .env.example .env
```

编辑 `.env` 文件：
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

### 3. 初始化数据库

1. 在 Supabase 控制台打开 SQL Editor
2. 复制 `supabase/migrations/001_initial_schema.sql` 内容
3. 执行 SQL 创建数据库表和安全规则

### 4. 导入种子数据

在 Supabase 控制台的 Table Editor 中：
1. 打开 `knowledge_nodes` 表
2. 点击 "Insert" → "Import data from CSV"
3. 选择 `cloudfunctions/initSeedData/data/` 目录下的 JSON 文件

或者使用 Supabase CLI：
```bash
supabase db seed
```

### 5. 开发运行

```bash
# 启动 H5 开发服务器
npm run dev:h5

# 访问 http://localhost:10086
```

### 6. 打包 APK

```bash
# 编译 H5
npm run build:h5

# 添加 Android 平台
npm run cap:add:android

# 同步代码
npm run cap:sync

# 打开 Android Studio
npm run cap:open:android
```

在 Android Studio 中：
1. 等待 Gradle 同步完成
2. 点击 Build → Build Bundle(s) / APK(s) → Build APK(s)
3. APK 文件在 `android/app/build/outputs/apk/debug/app-debug.apk`

## 项目结构

```
medlearn/
├── src/
│   ├── lib/
│   │   └── supabase/
│   │       ├── client.ts      # Supabase 客户端配置
│   │       └── types.ts       # TypeScript 类型定义
│   ├── services/
│   │   ├── auth.ts            # 认证服务
│   │   ├── knowledge.ts       # 知识点服务
│   │   ├── feynman.ts         # 费曼复述服务
│   │   ├── exam.ts            # 考试服务
│   │   ├── analytics.ts       # 数据分析服务
│   │   └── index.ts           # 服务导出
│   ├── pages/                 # 页面组件
│   ├── components/            # 通用组件
│   ├── constants/             # 常量定义
│   └── types/                 # 类型定义
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql  # 数据库 Schema
├── android/                   # Android 项目（自动生成）
├── capacitor.config.ts        # Capacitor 配置
├── package.json               # 项目依赖
├── .env.example               # 环境变量示例
└── AGENT.md                   # 开发规则文档
```

## 服务层 API

### AuthService
```typescript
import { AuthService } from './services'

// 邮箱登录
const result = await AuthService.loginWithEmail(email, password)

// 匿名登录
const result = await AuthService.loginAsGuest()

// 退出登录
await AuthService.logout()
```

### KnowledgeService
```typescript
import { KnowledgeService } from './services'

// 获取知识点列表
const { data, total } = await KnowledgeService.getNodes({
  subject: '内科学',
  page: 1,
  pageSize: 20,
})

// 搜索知识点
const nodes = await KnowledgeService.searchNodes('高血压')

// 获取考试题目
const questions = await KnowledgeService.getExamQuestions({
  nodeId: 'node-id',
  limit: 10,
})
```

### FeynmanService
```typescript
import { FeynmanService } from './services'

// 提交费曼复述
const result = await FeynmanService.submitRecord(userId, {
  nodeId: 'node-id',
  transcript: '用户的复述内容...',
  aiScore: {
    accuracy: 85,
    completeness: 70,
    clarity: 90,
    depth: 75,
  },
  feedback: 'AI 的反馈...',
})

// 获取用户记录
const { data, total } = await FeynmanService.getUserRecords(userId, {
  nodeId: 'node-id',
  page: 1,
})
```

### ExamService
```typescript
import { ExamService } from './services'

// 提交考试
const { success, result } = await ExamService.submitExam(userId, {
  questionIds: ['q1', 'q2', 'q3'],
  answers: [
    { questionId: 'q1', userAnswer: 0, isCorrect: true },
    { questionId: 'q2', userAnswer: 1, isCorrect: false },
  ],
  score: 70,
  weakNodes: ['node1'],
  duration: 300,
})

// 获取错题
const { data: wrongQuestions } = await ExamService.getWrongQuestions(userId, {
  retryCorrect: false,
})
```

### AnalyticsService
```typescript
import { AnalyticsService } from './services'

// 获取完整学习统计
const stats = await AnalyticsService.getLearningStats(userId)

console.log(stats.masteryDistribution)  // 掌握度分布
console.log(stats.weakPoints)           // 薄弱知识点
console.log(stats.streakDays)           // 连续学习天数
console.log(stats.weeklyFeynmanCount)   // 本周费曼复述数
```

## 免费额度

| 资源 | Supabase 免费额度 |
|------|------------------|
| 数据库存储 | 500MB |
| 文件存储 | 1GB |
| 月活用户 | 50,000 |
| API 请求 | 免费 |

对于 MVP 阶段，免费额度完全够用。

## 常见问题

### Q: Supabase 如何获取 URL 和 Key？
A: 在 Supabase 控制台 → Settings → API 中获取。

### Q: 如何在真机测试？
A: 使用 `npm run build:h5` 编译后，用 Capacitor 打包 APK 安装到手机。

### Q: 如何更新数据库 Schema？
A: 修改 SQL 文件后，在 Supabase 控plimentary 控制台的 SQL Editor 中执行新的 SQL。

### Q: 如何部署到生产环境？
A: 1. 在 Supabase 创建生产项目
   2. 更新 `.env` 中的配置
   3. 执行 `npm run build:h5 && cap sync`
   4. 在 Android Studio 中构建 Release APK

## 下一步

1. ✅ 后端架构已完成
2. ⏳ 开发前端页面
3. ⏳ 集成 AI 服务
4. ⏳ 测试和优化
5. ⏳ 发布 APK
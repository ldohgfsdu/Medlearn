# MedLearn

AI 驱动的医学思维训练移动应用，帮助医学生和规培医生通过费曼学习法和 VINDICATE 鉴别诊断框架建立系统化临床思维，而非死记硬背。

> **核心理念**: 致广大而尽精微，极高明而道中庸

## 技术栈

- **前端**: Taro 4 + React 18 + TypeScript
- **后端**: Supabase (PostgreSQL + Auth)
- **打包**: Capacitor (Android APK)

## 核心功能

- **费曼复述** - AI 评分和反馈，检验知识掌握程度
- **苏格拉底对话** - 追问式学习，深入理解机制
- **病例沙盒** - 渐进式病例分析，培养临床思维
- **推导链** - VINDICATE 框架训练，建立鉴别诊断能力
- **模拟考试** - 薄弱知识点诊断，精准查漏补缺
- **间隔重复** - SM-2 算法，科学记忆巩固

## 快速开始

```bash
# 安装依赖
npm install

# 配置环境变量
cp .env.example .env

# 启动开发服务器
npm run dev:h5

# 打包 APK
npm run cap:build:android
```

## 项目结构

```
src/
├── lib/supabase/    # Supabase 客户端
├── services/        # 业务服务层
├── pages/           # 页面组件
└── components/      # 通用组件
```

## 许可证

MIT
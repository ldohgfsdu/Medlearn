# MedLearn

AI 驱动的医学思维训练移动应用

## 技术栈

- **前端**: Taro 4 + React 18 + TypeScript
- **后端**: Supabase (PostgreSQL + Auth)
- **打包**: Capacitor (Android APK)

## 核心功能

- 费曼复述 - AI 评分和反馈
- 苏格拉底对话 - 追问式学习
- 病例沙盒 - 渐进式病例分析
- 推导链 - 临床思维训练
- 模拟考试 - 薄弱知识点诊断
- 间隔重复 - SM-2 算法

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
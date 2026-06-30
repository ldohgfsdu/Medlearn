# MedLearn 医学学习应用 - 实施计划

## 项目背景
为医学学习者打造一个基于「因果推导链 + 病例沙盒 + 费曼复述」的学习工具，帮助你理解医学本质而非死记硬背。

## 技术选型
- **前端**: React 19 + TypeScript 5 + Vite 8
- **样式**: Tailwind CSS 4
- **数据库**: IndexedDB (Dexie 4)
- **AI**: Claude API (Cloudflare Worker 代理)
- **图表**: Recharts
- **图标**: Lucide React
- **项目位置**: G:/MedLearn

## 实现阶段

### Phase 1: 基础框架搭建 (第1周)

#### 1.1 项目初始化
- 使用 Vite 创建 React + TypeScript 项目
- 配置 Tailwind CSS v4
- 安装依赖: react-router-dom, dexie, recharts, lucide-react

**关键文件**:
- `vite.config.ts` - Vite 配置（含代理配置）
- `index.css` - Tailwind 引入和全局样式
- `package.json` - 依赖管理

#### 1.2 数据层搭建
- 定义所有 TypeScript 类型（Knowledge, Case, Learning, AI）
- 初始化 Dexie 数据库和表结构
- 添加测试数据：3个内科学知识点，1个完整病例

**关键文件**:
- `src/types/knowledge.ts` - 知识节点、因果链类型
- `src/types/case.ts` - 病例数据类型
- `src/types/learning.ts` - 学习记录类型
- `src/types/ai.ts` - AI API 类型
- `src/db/db.ts` - Dexie 数据库初始化
- `src/db/seed.ts` - 种子数据（测试用）

#### 1.3 UI 框架搭建
- 左侧导航侧边栏（可折叠）
- 顶部 Header（主题切换、设置入口）
- 主内容区布局
- 暗色/亮色主题切换
- 响应式布局

**关键文件**:
- `src/components/layout/AppLayout.tsx` - 整体布局
- `src/components/layout/Sidebar.tsx` - 导航侧边栏
- `src/components/layout/Header.tsx` - 顶部栏
- `src/hooks/useTheme.ts` - 主题切换 Hook

#### 1.4 路由配置
配置页面路由：
- `/` - Dashboard（学情总览）
- `/knowledge` - KnowledgeMap（知识地图）
- `/pathway/:chainId` - Pathway（因果推导链）
- `/case/:caseId` - ClinicSandbox（病例沙盒）
- `/feynman/:nodeId` - FeynmanRecall（费曼复述）
- `/analytics` - Analytics（详细学情分析）

**关键文件**:
- `src/App.tsx` - 路由配置

---

### Phase 2: 因果推导链 (Pathway) - 第2周

#### 2.1 因果链数据设计
设计一个完整的因果推导链（以 COPD 为例）：
```
吸烟/有害颗粒暴露 → 气道慢性炎症 → 蛋白酶-抗蛋白酶失衡
→ 气道重塑 → 气流受限 → FEV1/FVC↓ → 气体陷闭
→ 肺过度充气 → 呼吸困难 → 活动耐力下降
```

每个步骤包含：
- 引导问题
- 多个选项（只有一个正确）
- 选择反馈（正确/错误 + 解释）
- 下一步链接

#### 2.2 核心组件开发
- PathwayContainer: 状态管理（当前步骤、历史记录）
- PathwayQuestion: 问题展示
- PathwayOptions: 选项选择（单选）
- PathwayFeedback: 选择后的反馈
- PathwayProgress: 进度条和步骤导航

#### 2.3 学习记录
- 记录用户的每一步选择
- 记录用时
- 保存到 IndexedDB

**关键文件**:
- `src/pages/Pathway.tsx` - 因果推导链页面
- `src/components/pathway/` - Pathway 相关组件
- `src/hooks/usePathway.ts` - Pathway 状态管理 Hook

---

### Phase 3: AI 集成基础 - 第3周

#### 3.1 AI 代理选择
推荐方案：Cloudflare Worker（免费，10万次/天）

Worker 代码负责：
- 接收前端请求
- 调用 Claude API
- 流式返回响应 (SSE)

#### 3.2 前端 AI 客户端
- 封装 fetch 请求
- 支持流式响应 (ReadableStream)
- 错误处理

#### 3.3 费曼复述基础版
- 用户输入区（文本域）
- 提交后调用 AI 评估
- 流式显示 AI 评估结果
- 评分和建议展示

**关键文件**:
- `src/services/ai/client.ts` - AI 客户端封装
- `src/services/ai/prompts.ts` - Prompt 模板
- `src/pages/FeynmanRecall.tsx` - 费曼复述页面
- `src/components/feynman/` - Feynman 相关组件

---

### Phase 4: 病例沙盒 (Clinic Sandbox) - 第4周

#### 4.1 病例数据模型
一个完整的病例包含：
- 主诉、现病史、既往史
- 体格检查（生命体征、各系统检查）
- 辅助检查（实验室、影像学）
- 分阶段解锁：病史 → 查体 → 检查 → 诊断 → 治疗

#### 4.2 分阶段诊疗流程
- 第1阶段：收集病史（展示信息）
- 第2阶段：体格检查（用户选择做哪些检查）
- 第3阶段：辅助检查（根据选择解锁结果）
- 第4阶段：诊断（用户输入 + AI 评估）
- 第5阶段：治疗方案

#### 4.3 核心组件
- CasePresentation: 病例信息展示
- InvestigationPanel: 检查选择面板（查体、实验室、影像）
- DiagnosisPanel: 诊断输入（含 AI 评估）
- TreatmentPanel: 治疗方案
- CaseTimeline: 诊疗进度时间线

**关键文件**:
- `src/pages/ClinicSandbox.tsx` - 病例沙盒页面
- `src/components/case/` - Case 相关组件
- `src/hooks/useCase.ts` - Case 状态管理 Hook

---

### Phase 5: 学情分析 (Analytics) - 第5周

#### 5.1 学习记录收集
- Pathway 学习记录
- Feynman 复述记录
- Case 诊疗记录
- 计算正确率、用时、薄弱点

#### 5.2 薄弱点检测算法
简单规则实现：
- 错误次数 > 2 次 → 标记为薄弱
- 同一知识点多次混淆 → 标记为概念混淆
- 长时间未复习 → 标记为需复习

#### 5.3 Dashboard 数据展示
- 学情总览卡片（总学习时长、完成知识点、正确率）
- 薄弱点列表
- 今日推荐学习
- 掌握度趋势图（Recharts）

#### 5.4 Analytics 页面
- 详细学习历史
- 各学科掌握度
- 时间分布统计
- 错误类型分析

**关键文件**:
- `src/pages/Dashboard.tsx` - 学情总览页面
- `src/pages/Analytics.tsx` - 详细分析页面
- `src/services/analytics.ts` - 学情分析服务
- `src/components/analytics/` - 分析相关组件

---

### Phase 6: 数据完善与优化 - 第6周起

#### 6.1 批量导入数据
- 呼吸系统：COPD、肺炎、肺结核、肺癌、支气管哮喘
- 循环系统：心衰、高血压、冠心病、心律失常
- 消化系统：消化性溃疡、肝硬化、急性胰腺炎

#### 6.2 AI 评估优化
- 费曼复述：更详细的评估维度
- 病例诊断：结构化评估标准
- 薄弱点分析：AI 辅助诊断

#### 6.3 云端同步
- Dexie Cloud 调研
- 用户身份方案
- 数据同步逻辑

#### 6.4 性能优化
- 代码分割
- 懒加载
- IndexedDB 索引优化

---

## 文件结构

```
G:/MedLearn/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Header.tsx
│   │   ├── ui/                    # 基础UI组件
│   │   ├── pathway/               # Pathway相关
│   │   ├── case/                  # Case相关
│   │   ├── feynman/               # Feynman相关
│   │   └── analytics/             # Analytics相关
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── KnowledgeMap.tsx
│   │   ├── Pathway.tsx
│   │   ├── ClinicSandbox.tsx
│   │   ├── FeynmanRecall.tsx
│   │   └── Analytics.tsx
│   ├── db/
│   │   ├── db.ts                  # Dexie初始化
│   │   ├── seed.ts                # 种子数据
│   │   └── repositories/          # 数据访问层
│   ├── services/
│   │   ├── ai/
│   │   │   ├── client.ts          # AI客户端
│   │   │   └── prompts.ts         # Prompt模板
│   │   └── analytics.ts           # 学情分析
│   ├── hooks/
│   │   ├── useTheme.ts
│   │   ├── usePathway.ts
│   │   ├── useCase.ts
│   │   └── useAnalytics.ts
│   ├── types/
│   │   ├── knowledge.ts
│   │   ├── case.ts
│   │   ├── learning.ts
│   │   └── ai.ts
│   ├── utils/
│   │   └── helpers.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── public/
├── worker/                        # Cloudflare Worker
│   └── index.ts
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## 启动命令

```bash
# 进入项目目录
cd G:/MedLearn

# 开发服务器
/g/npm run dev

# 构建
/g/npm run build

# 预览
/g/npm run preview
```

## 验证步骤

### Phase 1 完成标志
- [ ] 项目能正常启动 (`npm run dev`)
- [ ] 页面切换正常
- [ ] 暗色/亮色主题切换正常
- [ ] 侧边栏展开/折叠正常

### Phase 2 完成标志
- [ ] 能进入 Pathway 页面
- [ ] 能看到因果推导链的完整流程
- [ ] 选择选项后有反馈
- [ ] 学习记录保存到 IndexedDB

### Phase 3 完成标志
- [ ] AI 代理能正常工作
- [ ] 能调用 Claude API 并获得响应
- [ ] 费曼复述页面能输入并获得 AI 评估

### Phase 4 完成标志
- [ ] 能进入病例沙盒
- [ ] 能看到完整病例
- [ ] 分阶段解锁机制正常
- [ ] 能完成整个诊疗流程

### Phase 5 完成标志
- [ ] Dashboard 显示学情数据
- [ ] 薄弱点检测正常
- [ ] 图表正常显示

## 关键约束

1. **Node.js**: 使用 G:/node.exe (v24.16.0)
2. **项目位置**: 所有文件放在 G:/MedLearn/
3. **开发环境**: Windows 11
4. **浏览器**: Chrome/Edge (支持 IndexedDB)
5. **AI 代理**: 前期使用 Cloudflare Worker 免费版

## 下一步行动

现在可以开始 Phase 1 的实施。让我开始项目初始化。
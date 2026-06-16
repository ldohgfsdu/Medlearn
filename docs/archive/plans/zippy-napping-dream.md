# MedLearn UI 重设计 — 微信 PC 风格

## 核心设计变更

将当前的 **「侧边栏 + 顶栏 + 内容区」** 布局改为 **「图标导航栏 + 列表面板 + 主内容区」** 三栏布局，模仿微信 PC 端的交互范式。

### 布局结构 (App.tsx)

```
┌──────────┬─────────────────┬───────────────────────────────────┐
│ 48px     │ 260-320px       │  flex-1                           │
│ 图标导航  │ 列表面板         │  主内容区                          │
│          │                 │                                   │
│ [头像]   │ 搜索框           │  (根据左栏选中的模块动态显示)        │
│ ──────── │ ─────────────── │                                   │
│ 🏠 总览  │ 今日推荐...      │  Dashboard: 统计卡片 + 推荐列表     │
│ 🧠 知识  │ 推导链列表...    │  Knowledge: 系统 > 章节树           │
│ 💬 费曼  │                 │  Feynman: 节点列表 > 复述详情       │
│ 🔬 病例  │                 │  Case: 病例列表 > 诊疗流程          │
│ 📝 考试  │                 │  Exam: 考试列表 > 答题 > 结果       │
│ 📊 数据  │                 │  Analytics: 图表面板                │
│ ⚙️ 设置  │                 │  Settings: 配置表单                 │
└──────────┴─────────────────┴───────────────────────────────────┘
```

### 交互逻辑

**导航栏 (48px 宽)**
- 纯图标，无文字，纵向排列
- 选中项：左侧 3px 指示条 + 背景高亮
- 顶部放 App Logo（小尺寸），底部放设置入口

**列表面板 (260-320px)**
- 顶部：搜索框 + 筛选/操作按钮
- 中间：列表项（卡片/列表混排），每项显示摘要信息
- 选中项高亮背景
- 不同模块的列表内容：
  - **学情总览**：最近学习记录、AI 推荐项
  - **知识地图**：系统 > 章节的树状列表（精简版）
  - **费曼复述**：知识点列表（按系统分组）
  - **病例沙盒**：病例列表（按系统分组）
  - **模拟考试**：按系统分组的考试入口
  - **学习分析**：无列表（直接显示图表）
  - **设置**：无列表（直接显示配置项）

**主内容区**
- 选中列表项后显示详情
- 无选中时显示该模块的概览/引导页

### 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/App.tsx` | 重写 | 三栏布局 + 模块状态管理 |
| `src/components/layout/Sidebar.tsx` | 重写 → `NavRail.tsx` | 48px 图标导航栏 |
| `src/components/layout/ListPanel.tsx` | **新建** | 260-320px 列表面板 |
| `src/components/layout/PanelItem.tsx` | **新建** | 列表项组件 |
| `src/index.css` | 修改 | 新增 CSS 变量和样式 |
| `src/pages/Dashboard.tsx` | 重写 | 列表面板 + 主内容区 |
| `src/pages/KnowledgeMap.tsx` | 重写 | 列表面板（系统树）+ 主内容区 |
| `src/pages/FeynmanRecall.tsx` | 重写 | 列表面板（节点列表）+ 主内容区 |
| `src/pages/feynman/NodeList.tsx` | 删除 | 逻辑移入 FeynmanRecall |
| `src/pages/feynman/FeynmanDetail.tsx` | 修改 | 作为主内容区渲染 |
| `src/pages/ClinicSandbox.tsx` | 重写 | 列表面板 + 主内容区 |
| `src/pages/case/CaseList.tsx` | 删除 | 逻辑移入 ClinicSandbox |
| `src/pages/case/CaseDetail.tsx` | 修改 | 作为主内容区渲染 |
| `src/pages/Exam.tsx` | 重写 | 列表面板 + 主内容区 |
| `src/pages/exam/ExamList.tsx` | 修改 | 作为列表面板内容 |
| `src/pages/exam/ExamActive.tsx` | 修改 | 作为主内容区（全宽） |
| `src/pages/exam/ExamResult.tsx` | 修改 | 作为主内容区 |
| `src/pages/Analytics.tsx` | 小改 | 适配新布局 |
| `src/pages/Settings.tsx` | 小改 | 适配新布局 |

### 设计细节

**色彩方案**
- 导航栏：深色底 (`#1e293b` 暗色 / `#f8fafc` 亮色)
- 列表面板：略浅于主内容区
- 主内容区：最浅底色
- 选中态使用应用主题色 (indigo-500) 低透明度背景

**列表项样式**
- 高度 64-72px，左缩进 16px
- 标题 14px 加粗 + 摘要 12px 灰色
- 选中：左边 3px 色条 + 背景色变化
- Hover：轻微背景变化

**响应式**
- 最小窗口宽度：900px
- 图标导航栏固定 48px
- 列表面板最小 240px，最大 320px
- 内容区自适应

### 实施顺序

1. 修改 `index.css` — 新增 CSS 变量和布局样式
2. 创建 `NavRail.tsx` — 48px 图标导航栏
3. 创建 `ListPanel.tsx` + `PanelItem.tsx` — 列表面板组件
4. 重写 `App.tsx` — 三栏布局骨架
5. 重写各页面组件 — 适配新布局
6. 清理旧文件

### 分步实施

**Step 1: CSS + 布局骨架**
- 新增 CSS 变量和布局样式
- NavRail 组件
- ListPanel 组件
- App.tsx 三栏布局

**Step 2: Dashboard + KnowledgeMap 页**
- Dashboard 列表（最近记录 + AI 推荐）
- KnowledgeMap 列表（系统树）

**Step 3: Feynman + Case 页**
- Feynman 列表（知识点）+ 详情
- Case 列表（病例）+ 详情

**Step 4: Exam + Analytics + Settings**
- Exam 列表 + 答题 + 结果
- Analytics 适配
- Settings 适配

**Step 5: 清理**
- 删除旧文件
- 确保所有导航正确

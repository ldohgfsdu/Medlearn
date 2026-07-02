# MedLearn Design Context

本文件是 MedLearn 视觉设计语言的唯一权威来源。token 定义在 `constants/theme.ts`、`constants/textbookEditorial.ts`、`constants/layout.ts`、`constants/pageStyles.ts`，本文件规定它们的语义和用法。UI 工作还需满足 `.agents/skills/medlearn-review-ui/SKILL.md` 的 Product Constraints。

## 1. 设计方向

- **气质**：临床、克制、可信，接近编辑式学习笔记，而非游戏化学习产品。
- **主色**：墨绿 `Colors.primary` + 暖白背景 `Colors.background` + 陶土 `Colors.accent`，不临时增加颜色。
- **层级**：大标题建立入口，重点摘要形成唯一视觉焦点，其余信息依靠字号、留白和分隔线组织。
- **内容**：先呈现可复习的短要点，教材原文只作为按需展开的参考资料。
- **克制**：靠字号、衬线和留白创造层次，不靠粗体、阴影、全大写或装饰字距。

## 2. 色彩语义

| Token | 用途 | 何时用 |
|---|---|---|
| `Colors.primary[500-900]` | 品牌主色墨绿 | 主按钮、强调链接、活跃态、品牌锚点 |
| `Colors.ink` `#17332C` | 深墨绿 | 高强调表面（Hero、输入域聚焦）、章节级锚点 |
| `Colors.background` `#FAF9F5` | 暖白 | 全局背景 |
| `Colors.surface` `#FFFDF9` | 象牙白 | 卡片、输入域、Sheet |
| `Colors.surfaceVariant` | 浅米 | 次级表面、分组容器 |
| `Colors.border` `#E8E6DC` | 米色边线 | 静态卡片 hairline 边框、分隔线 |
| `Colors.textPrimary` `#141413` | 近黑 | 正文、标题 |
| `Colors.textSecondary` `#4A4945` | 深灰 | 次级正文、说明 |
| `Colors.textTertiary` `#6B6A64` | 中灰 | 元信息、占位 |
| `Colors.accent` `#E27A57` | 陶土 | 仅用于需要暖色强调的极少数场景，不替代 primary |

### 语义色

| Token | 用途 |
|---|---|
| `Colors.success` | 成功、正确答案、已掌握 |
| `Colors.warning` | 警告、一般掌握度 |
| `Colors.error` | 错误、安全风险、未掌握 |
| `Colors.info` | 中性提示、良好掌握度 |

### 掌握度色 `Colors.mastery`

| 等级 | 色值 | 分数区间 |
|---|---|---|
| `excellent` | `#2D8A68` | 90-100% 精通 |
| `good` | `#347C91` | 70-89% 良好 |
| `fair` | `#C6832B` | 50-69% 一般 |
| `weak` | `#D76F43` | 30-49% 薄弱 |
| `fail` | `#C6534A` | 0-29% 未掌握 |

通过 `getMasteryColor(score)` 取色，不要硬编码分数区间。

### 教材阅读表面 `TextbookEditorial`

教材详情页使用独立的编辑式 token：象牙纸 `paper`、深墨 `ink`、陶土 `accent` `#B45309`。仅用于教材阅读场景，不扩散到主 app UI。

## 3. 字体语义

### 字族 `FontFamily`

| 字族 | 用途 |
|---|---|
| `FontFamily.serif` (Georgia / Noto Serif SC) | **所有标题**（display/title）、**数字数据**、教材阅读正文 |
| `FontFamily.sans` (Inter / System) | 标签、按钮文字、功能元素、UI 元信息 |

### 字号层级 `Typography`

**标题** — serif + 600 字重，紧凑行高 (~1.1x)：
- `displayLarge` 48/53 — 首屏大标题
- `displayMedium` 36/40 — 章节级 Hero
- `titleLarge` 20/24 — 页面标题
- `titleMedium` 16/20 — 区块标题
- `titleSmall` 14/18 500 — 小节标题

**正文** — 400 字重，宽松行高 (1.4x)：
- `bodyLarge` 16/22 — 重要正文
- `bodyMedium` 15/21 — **默认正文，最小字号**
- `bodySmall` 13/18 — 仅用于元信息、时间戳、辅助说明，**不用于正文段落**

**标签** — 中等行高：
- `labelLarge` 14/20 — 按钮文字、主标签
- `labelMedium` 13/18 — 次级标签
- `labelSmall` 11/15 500 — 最小标签

**数字** — serif + 600 字重，赋予"学术出版数据"质感：
- `numberXL` 24/30 — Hero 核心数据
- `numberLarge` 20/24 — 卡片数据
- `numberMedium` 16/20 — 行内数据

### 字重红线

- **最大字重 600**。禁止 700/800/900。
- 标题统一 serif 600；正文和标签 400/500。
- 装饰 `letterSpacing` 仅用于验证码输入，禁止全大写 `textTransform`。

## 4. 间距节奏

4px 网格 `Spacing`：

| Token | 值 | 用途 |
|---|---|---|
| `xs` | 4 | 紧凑行内间距、图标缝隙 |
| `sm` | 8 | 标签与正文间距、卡片内小间距 |
| `md` | 12 | 区块内间距、列表行间距 |
| `base` | 16 | 卡片内边距 `Layout.cardPadding`、默认间距 |
| `lg` | 20 | 区块间距 `Layout.sectionGap`、页面边距 `Layout.screenPaddingX` |
| `xl` | 24 | 大区块间距 |
| `2xl` | 32 | Hero 间距 |
| `3xl`+ | 40+ | 首屏大间距 |

页面边距统一 `Layout.screenPaddingX = 20`，卡片内边距统一 `Layout.cardPadding = 16`，不要硬编码。

## 5. 组件层级

### 表面优先级

1. **Hero** — 唯一最高强调面，深墨绿背景 `Colors.ink` + 大字标题 + 可选阴影。每屏最多一个。
2. **静态卡片** — hairline 边框（`borderWidth: 1` + `Colors.border`），**不用阴影**。
3. **输入域** — 可选轻阴影，聚焦时 `Colors.ink` 边框。
4. **Sheet/Modal** — 浮层用 `Shadows.sheet`。

### 卡片 vs 分隔线

- 同级内容优先用分隔线 `StyleSheet.hairlineWidth` + `Colors.border`，不用卡片套卡片。
- 静态内容卡片一律 hairline 边框，不用阴影。
- 阴影仅用于 Hero、输入域、Sheet/Modal。

### 圆角 `BorderRadius`

- `sm` 4 — 标签、小徽章
- `md` 8 — 输入域、小组件
- `lg` 12 — 卡片 `Layout.cardRadius`
- `xl` 16 — 大卡片
- `2xl` 24 — Sheet
- `full` 9999 — 按钮、胶囊

### 触达区

- 可点击区域最小高度 **44px**。
- 主按钮 `ComponentSize.buttonMinHeight = 48`。
- 列表行 `Layout.listRowHeight = 60` / `listRowHeightCompact = 52`。

## 6. 界面规则

- 正文至少 15px，中文正文行高约 1.65（`Typography.bodyMedium` lineHeight 21）。
- 可点击区域最小高度 44px。
- 页面最多保留一个高强调内容面，避免所有模块都做成卡片。
- 同级内容优先使用分隔线，不使用卡片套卡片。
- 图标使用 `Ionicons`，不使用 emoji 充当功能图标。
- 标题不为装饰而配图标；图标只用于导航、状态和明确操作。
- 阴影只用于确有悬浮层级的元素（Hero、输入域、Sheet），不用于普通内容容器。
- 不编造数据、统计、评价或装饰性内容。
- 数字数据用 serif-600 字号样式，不用粗体强调。

## 7. 知识详情页

- 复合知识点先按真实子主题分组，再展示章节。
- 首屏只展示核心摘要和子主题目录。
- 每章默认展示 3 至 4 条精炼要点。
- 长篇教材内容通过"查看教材原文"单独展开。
- 不同疾病或毒物的同名章节不得跨主题合并。

## 8. 评审顺序

每次 UI 调整依次检查：

1. 功能性：信息是否更容易找到和操作。
2. 细节执行：间距、对齐、字号和点击区域是否统一。
3. 视觉层级：用户是否能一眼看到当前最重要的信息。
4. 哲学一致性：是否符合临床编辑式学习体验。
5. 创新性：是否有独特表达，同时避免影响可用性。

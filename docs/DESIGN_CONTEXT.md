# MedLearn Design Context

本文件是 MedLearn UI 语义、使用边界和评审规则的**唯一权威来源**。

token 的具体数值以 `constants/theme.ts`、`constants/textbookEditorial.ts`、`constants/layout.ts`、`constants/pageStyles.ts` 代码为准；token 的语义、适用范围、禁止用法以本文档为准。

当文档与代码出现冲突时，不允许临时择一执行，应视为 **design-token drift**：

1. 若是数值不一致，更新文档或 token 代码使其一致；
2. 若是语义不一致，优先按本文档修正实现；
3. UI PR / agent 任务必须报告该冲突，不得静默绕过。

UI 工作还需满足 `.agents/skills/medlearn-review-ui/SKILL.md` 的 Product Constraints。

## 1. 设计方向

- **气质**：临床、克制、可信，接近编辑式学习笔记，而非游戏化学习产品。
- **主色**：墨绿 `Colors.primary` + 暖白背景 `Colors.background` + 陶土 `Colors.accent`，不临时增加颜色。
- **层级**：大标题建立入口，重点摘要形成唯一视觉焦点，其余信息依靠字号、留白和分隔线组织。
- **内容**：先呈现可复习的短要点，教材原文只作为按需展开的参考资料。
- **克制**：靠字号、衬线和留白创造层次，不靠粗体、阴影、全大写或装饰字距。

## 2. 页面术语

为避免后续 agent 把"知识详情页"和"教材阅读页"混为一个页面，统一术语：

- **知识详情页**：以知识点复习为主，首屏展示 AI 摘要、子主题目录、精炼要点。使用 `Colors.*` 主 UI token。
- **教材阅读页 / 教材原文区**：以教材原文阅读为主，使用 `TextbookEditorial.*` token。
- **TextbookOriginalBlock**：知识详情页内按需展开的教材原文入口，不等于完整教材阅读页。展开后切换到 `TextbookEditorial` 域 token。

## 3. 色彩语义

### 主色与中性色

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
| `Colors.accent` `#E27A57` | 陶土 | 学习行动色：主操作按钮背景、任务温度点。不替代 primary |

### 行动色分工 — 陶土 vs 墨绿

首页主行动使用陶土 `accent`；医学结构锚点、章节路径、证据定位和输入聚焦状态使用 `ink` / `primary`。

- **学习行动 = 陶土 `accent`**：首页主 CTA、今日任务点、学习行动按钮。
- **医学结构 / 证据 / 导航锚点 = 墨绿 `ink` / `primary`**：教材证据定位、错题打开、章节锚点、输入聚焦、底部导航 active。

`accent` 不替代 `primary`，`primary` 也不重新承担首页大面积 Hero 背景。

**对比度注意：** `accent #E27A57` 与 `Colors.ink #17332C` 约 4.6:1，通过 WCAG AA 普通文字要求；与 `Colors.surface #FFFDF9` 约 2.9:1，不通过。陶土做按钮背景时，文字必须用 `Colors.ink` 或 `Colors.textPrimary`（更稳，约 6.3:1），不得用 `Colors.surface`。

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

### 教材阅读表面 `TextbookEditorial` — 跨域隔离

教材详情页使用独立的编辑式 token：象牙纸 `paper`、深墨 `ink`、陶土 `accent` `#B45309`。

**跨域使用硬性禁止：**
- 禁止在主 App UI 中直接使用 `TextbookEditorial.*`。
- 禁止在教材阅读页中直接使用 `Colors.accent`。
- 两个 `accent`（`Colors.accent #E27A57` 与 `TextbookEditorial.accent #B45309`）色值不同，混用会导致一页内两个陶土色互相打架。
- 跨域复用必须新增语义 token，不得直接引用对方域的 token。

## 4. 字体语义

### 字族分层 — 内容层 vs 操作层

`FontFamily.serif`（Georgia / Noto Serif SC）与 `FontFamily.sans`（Inter / System）的分工按**信息层级**划分，不是"所有标题都 serif"。

| 层级 | 字族 | 用途 |
|---|---|---|
| **知识内容层** | `serif` | 内容标题、章节标题、知识点标题、教材阅读正文、医学内容数字（剂量、页码、化验值） |
| **操作界面层** | `sans` | 导航栏标题、Tab、首页 Hero、按钮文字、表单标签、列表元信息、仪表盘数字、Dialog |

**判断规则：** 这块文字是在"呈现学习内容"还是在"提供操作界面"？前者 serif，后者 sans。

**示例：**
- 知识详情页的"肺炎链球菌肺炎"标题 → serif（内容标题）
- 底部 Tab"学习/病例/我的" → sans（导航）
- 列表行的"肺炎链球菌肺炎"知识点标题 → serif（内容标题）
- 列表行的"3 个要点 · 第 42 页"元信息 → sans（功能元信息）
- "开始病例"按钮文字 → sans（操作）
- 首页 Hero 标题与说明 → sans（操作界面层，不是教材阅读层）
- 学习报告 / 病例记录中的统计数字 → sans + `tabular-nums`（仪表盘数字）

### 字号层级 `Typography`

**标题尺度** — 600 字重，紧凑行高 (~1.1-1.2x)；字族在调用处按内容层/操作层显式指定：
- `displayLarge` 48/53 — 首屏大标题
- `displayMedium` 36/40 — 章节级 Hero
- `titleLarge` 20/24 — 页面标题
- `titleMedium` 16/20 — 区块标题
- `titleSmall` 14/18 500 — 小节标题

**正文** — 400 字重，宽松行高（1.5-1.6x），适合中文医学知识点密度阅读：
- `bodyLarge` 16/24 — 重要正文
- `bodyMedium` 15/24 — **默认正文，最小字号**
- `bodySmall` 13/18 — 仅用于元信息、时间戳、辅助说明，**不用于正文段落**

**标签** — 中等行高：
- `labelLarge` 14/20 — 按钮文字、主标签
- `labelMedium` 13/18 — 次级标签
- `labelSmall` 11/15 500 — 最小标签

**数字尺度** — 600 字重；字族按语义在调用处组合：
- `numberXL` 24/30 — Hero 核心数据
- `numberLarge` 20/24 — 卡片数据
- `numberMedium` 16/20 — 行内数据
- 医学内容数字 → `FontFamily.serif` + `Typography.number*`
- 仪表盘 / 进度 / 计数 → `FontFamily.sans` + `Typography.number*` + `fontVariant: ['tabular-nums']`

### 字重红线

- **最大字重 600**。禁止 700/800/900。
- 知识内容标题用 serif 600；操作界面标题用 sans 600；正文 400；标签 400/500。
- 操作界面文字（按钮、Tab、导航、Dialog）用 sans，主强调可用 600，次级用 500。
- 装饰 `letterSpacing` 仅用于验证码输入，禁止全大写 `textTransform`。

### token 组合写法

`Typography.*` 只定义字号、行高、字重，**不含 fontFamily**。组件必须显式组合 `FontFamily.*` + `Typography.*`，否则 serif/sans 分层会失效。

```ts
// 正确
title: { ...Typography.titleMedium, fontFamily: FontFamily.serif }
meta:   { ...Typography.labelMedium, fontFamily: FontFamily.sans }

// 错误 — 只套字号 token，字族未指定
title: { ...Typography.titleMedium }
```

### 系统弹窗

- 禁止使用 `Alert.alert` 作为产品内确认/提示入口。
- 统一使用 `AppDialogProvider` + `appAlert()`，保持暖白卡片、无衬线排版与 MedLearn 按钮语义。
- 连续弹窗必须排队顺序展示，后触发的 Dialog 不可覆盖当前可见 Dialog。

## 5. 间距节奏

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

## 6. 组件层级

### 表面优先级

1. **Hero** — 唯一最高强调面，深墨绿背景 `Colors.ink` + 大字标题 + 可选阴影。每屏最多一个。
2. **静态卡片** — hairline 边框（`borderWidth: 1` + `Colors.border`），**不用阴影**。
3. **输入域** — 可选轻阴影，聚焦时 `Colors.ink` 边框。
4. **Sheet/Modal** — 浮层用 `Shadows.sheet`。

### Hero 使用边界

Hero 要少，才有重量。**只允许用于：**
1. 首页 / 学习总览的核心状态；
2. 知识详情页首屏核心摘要；
3. 阶段性结果页（如病例评分总结）。

**禁止用于：**
1. 普通列表页；
2. 设置页；
3. 搜索结果页；
4. 每个二级模块的常规标题区。

### 卡片 vs 分隔线 — 双向规则

**优先用分隔线的情况：**
- 同一章节下的知识点列表；
- 同一组元信息；
- 同级短条目；
- 教材原文段落。

**必须用卡片的情况：**
1. 内容需要作为一个整体被点击；
2. 内容有独立状态（掌握度、进度、错误数）；
3. 内容需要和周围背景形成可扫描分组；
4. Sheet / 输入域 / 复习任务块等有明确操作边界的模块。

**禁止：** 卡片套卡片。同级内容用分隔线组织，不嵌套卡片。

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

## 7. 组件 Recipes

以下组件模板规定结构、token 选择和禁止项。实现时按模板执行，不重新发明。所有字体必须显式组合 `FontFamily.*` + `Typography.*`。

### Hero

- 用途：首页/总览/结果页的核心状态陈述。
- 结构：
  - background: `Colors.surface`（浅纸面，不压屏）
  - border: `Colors.border` hairline
  - no shadow
  - title: `FontFamily.serif` + `Typography.titleLarge` 或自定义 22/28，color `Colors.ink`（墨绿做结构锚点）
  - subtitle: `FontFamily.serif` + `Typography.bodyMedium`，color `Colors.textSecondary`
  - label dot: `Colors.accent`（陶土做今日任务温度点）
  - label text: `FontFamily.sans` + `Typography.labelMedium`，color `Colors.accent`
  - action: `FontFamily.sans` + `Typography.labelLarge`，胶囊按钮 `Colors.accent` 背景 + `Colors.surface` 文字（陶土做主操作色）
  - meta: `FontFamily.sans` + `Typography.labelSmall`，color `Colors.textTertiary`
- 文案：陈述句，不喊口号，不用感叹号。
- 禁止：深墨绿大面积背景、渐变背景、多按钮堆叠、emoji、全大写、发光效果、玻璃拟态、装饰性 orb。

### KnowledgeSummaryBlock

- 用途：知识详情页首屏唯一重点摘要。
- 结构：
  - title: `FontFamily.serif` + `Typography.titleMedium`
  - summary: `FontFamily.serif` + `Typography.bodyMedium`
  - max bullets: 3-5
  - background: `Colors.surface`
  - border: `Colors.border` hairline
  - no shadow
- 禁止：emoji、渐变背景、超过 600 字重、多色标签堆叠。

### KnowledgePointRow

- 用途：章节/搜索/复习列表中的知识点入口。
- 结构：
  - title: `FontFamily.serif` + `Typography.titleSmall` 或 `bodyMedium`
  - meta: `FontFamily.sans` + `Typography.labelMedium` + `Colors.textTertiary`
  - optional status: `MasteryBadge`
  - separator: hairline `Colors.border`，不用卡片嵌套
- 交互：整行可点击，触达 ≥44px。
- 禁止：每个知识点包成重卡片、用 emoji 标记疾病/系统。

### ChapterDirectoryRow

- 用途：教材目录的章/节/子节行。
- 结构：
  - 章标题: `FontFamily.serif` + `Typography.titleMedium`
  - 节/子节标题: `FontFamily.serif` + `Typography.titleSmall` 或 `bodyMedium`
  - 元信息（"X 节"/"独立章节"/页码）: `FontFamily.sans` + `Typography.labelMedium` + `Colors.textTertiary`
  - 分隔线: hairline `Colors.border`，不用卡片嵌套
- 交互：整行可点击，触达 ≥44px。
- 禁止：每行加卡片阴影、为装饰给标题加图标。

### SectionHeader

- 用途：页面内区块标题，如"核心摘要""相关章节""教材原文"。
- 结构：
  - title: `FontFamily.serif` + `Typography.titleMedium`
  - optional action: `FontFamily.sans` + `Typography.labelMedium`
- 禁止：为了装饰加图标、使用全大写、使用 700+ 字重。

### TextbookOriginalBlock

- 用途：知识详情页内按需展开的教材原文入口。
- 结构：
  - 折叠态：单行入口"查看教材原文" + 页码范围，`FontFamily.sans` + `Typography.labelLarge`
  - 展开态：`FontFamily.serif` + `Typography.bodyLarge` 阅读正文，切换到 `TextbookEditorial` 域 token
  - 边框: hairline `Colors.border`
- 禁止：默认全展开、与 AI 摘要混在同一视觉层级、用 `Colors.accent` 替代 `TextbookEditorial.accent`。

### InlineEvidenceLink

- 用途：连接摘要要点与教材证据的页码/证据入口。
- 结构：
  - text: `FontFamily.sans` + `Typography.labelMedium`
  - color: 主 UI 域用 `Colors.primary[700]`，教材阅读域用 `TextbookEditorial.accent`
- 禁止：无证据时显示入口、编造页码、把证据链接做成高强调按钮。

### MasteryBadge

- 用途：掌握度标签。
- 结构：`FontFamily.sans` + `Typography.labelSmall` + `getMasteryColor(score)` 圆点或文字。
- 禁止：硬编码分数区间色值、用 emoji 替代色点。

### SearchInput

- 用途：搜索框。
- 结构：`Colors.surface` 背景 + hairline 边框 + 左侧 search 图标 + 占位 `Colors.textTertiary`。输入文字 `FontFamily.sans` + `Typography.bodyLarge`。
- 聚焦：`Colors.ink` 边框，可选轻阴影。
- 禁止：渐变边框、neon 高亮。

### EmptyState

- 用途：无数据时的占位。
- 结构：
  - description: `FontFamily.sans` + `Typography.bodyMedium` + `Colors.textSecondary`
  - action（可选）: `FontFamily.sans` + `Typography.labelLarge` + `Colors.primary[700]`
  - 居中，留白为主
- 禁止：假统计、假推荐、假进度、夸张插画、emoji。

### ErrorState

- 用途：加载失败、同步失败、资源缺失。
- 结构：
  - 发生了什么: `FontFamily.sans` + `Typography.bodyMedium` + `Colors.textPrimary`
  - 是否影响学习: `FontFamily.sans` + `Typography.labelMedium` + `Colors.textTertiary`
  - 用户可以做什么: 重试按钮 / 联系反馈入口
- 禁止：只显示"出错了"无后续、用假数据填充、隐藏错误。

### LoadingState

- 用途：数据加载中。
- 结构：骨架屏（hairline 边框 + `Colors.surfaceVariant` 填充块）或低强调文本"正在加载…"（`FontFamily.sans` + `Typography.bodyMedium` + `Colors.textTertiary`）。
- 骨架屏规则：
  - 只模拟真实内容结构，不额外创造不存在的模块；
  - 骨架块圆角使用 `BorderRadius.sm` 或 `md`；
  - 不得显示假标题、假数字、假进度。
- 禁止：夸张动效、旋转转盘占满屏、假数据预填。

### BottomTabBar

- 用途：移动端底部主导航，浮动 Pill 形态，全 App 通用。
- 结构：
  - 容器（`tabBarWrap`）：占位（非 absolute），背景 `Colors.background`（与页面同色，pill 浮在同色背景上），顶部 `Spacing.md`，左右 21，底部 `insets.bottom`（无 safe area 时 `Spacing.sm`）。
  - Pill：高 62、圆角 36、`Colors.surface` 背景 + hairline 边框 `Colors.border`，**不加阴影**，内 padding `Spacing.xs`，item 间 gap `Spacing.xs`。
  - Tab item：`flex:1`、高 54（pill 高 - 上下 padding）、圆角 26、垂直居中、gap 3。
  - icon：Ionicons，size 20，active 用 outline→filled 切换。
  - label：`FontFamily.sans` + 11/14，active `600` + `Colors.surface`，inactive `500` + `Colors.neutral[400]`。
  - active 态：`Colors.ink` 实色填充 + surface 图标/文字。
  - inactive 态：透明背景 + `neutral.400` 图标/文字。
- 行动色分工：active 用 `Colors.ink`（医学结构/导航锚点语义），**不用陶土 `accent`**（陶土仅用于学习行动）；不用 `primary` 渐变。
- 留白规则：tab bar 占位，内容自动停在其上方；滚动容器 `paddingBottom` 叠加 `FLOATING_TAB_BAR_BASE_HEIGHT + insets.bottom + Spacing.lg` 作为安全余量，避免末尾内容贴边。
- 可访问性：每个 tab item `accessibilityRole="button"`、`accessibilityState={focused ? { selected: true } : {}}`、`accessibilityLabel` 为 tab 标题。
- 禁止：
  - 给 pill 或 active item 加阴影/elevation（浮动靠 hairline 边框与同色背景区分，不靠阴影）。
  - 用陶土 `accent` 或 `primary` 渐变做 active 态。
  - 用 emoji 作为 tab 图标。
  - 手写状态栏（StatusBar 组件由 expo 默认管理）。
  - 把 `href: null` 的隐藏路由渲染成 tab item。

### PageHeader

- 用途：统一全 App 各页顶部 header 形态，防止 header 越改越散。
- 形态分四种，按页面层级选择：
  1. **Tab 根页**：无 back，显示页面标题（serif），可选右侧操作按钮。由 `(tabs)/_layout.tsx` 的 `headerTitle` / `headerRight` 统一配置，页面不自定义 topBar。
  2. **二级页（从 Tab push）**：左侧 back 按钮 + 当前页面标题；标题应体现当前位置，不用上级页面名。
  3. **内容阅读页**：可显示小型 eyebrow label（`FontFamily.sans` + `labelSmall` + `inkFaint`）+ 大标题（serif）+ subtitle/meta；左侧 back。
  4. **首页**：brandRow（`FontFamily.sans` 600 品牌名）+ 头像按钮；问候语作为低强调环境文本，不占 header 位。
- token：标题用 `FontFamily.serif` + `Typography.titleLarge`（20/24 600）；eyebrow/操作按钮用 `FontFamily.sans`；背景 `Colors.background`，无底边线（靠下方 content `paddingTop` 留白分隔）。
- 禁止：
  - **Tab 根页显示 back 按钮**（用户会疑惑"在根页还是二级页"）。
  - 同一页面同时出现多个同级大标题。
  - 二级页标题沿用上级页面名（应体现当前位置）。
  - header 加底边线/阴影（除非设计稿明确要求浮层 header）。
  - 自定义 topBar 覆盖 Tab 根页的标准 header（应通过 `_layout.tsx` 配置）。

## 8. 知识详情页规则

- 复合知识点先按真实子主题分组，再展示章节。
- 首屏只展示核心摘要和子主题目录。
- 每章默认展示 3 至 4 条精炼要点。
- 长篇教材内容通过"查看教材原文"单独展开。
- 不同疾病或毒物的同名章节不得跨主题合并。
- 教材原文与 AI 摘要不得混在同一视觉层级。

## 9. 状态设计

MedLearn 是知识产品，不能为了界面完整去编内容。状态设计遵循以下规则：

- **空状态**：只说明当前没有什么，以及用户下一步能做什么。不使用假统计、假推荐、假进度。
- **加载状态**：使用骨架屏或低强调文本，不使用夸张动效。
- **错误状态**：必须包含三要素 — 发生了什么、是否影响学习、用户可以做什么。
- **缺失教材证据**：不显示"参考原文"入口，不编造页码。
- **远端数据为空**：显示 EmptyState，不用缓存数据伪装存在。
- **AI 摘要生成中**：显示 LoadingState，不预填假摘要。

## 10. 禁止模式

集中反例清单，review 时一眼可抓：

- 禁止卡片套卡片。
- 禁止每个 section 都加阴影。
- 禁止用 emoji 作为功能图标。
- 禁止为了装饰给标题加图标。
- 禁止大面积渐变。
- 禁止玻璃拟态。
- 禁止 neon / 高饱和蓝紫色。
- 禁止全大写标签。
- 禁止 700+ fontWeight。
- 禁止没有真实数据的统计卡片。
- 禁止把教材原文和 AI 摘要混在同一视觉层级。
- 禁止在主 App UI 使用 `TextbookEditorial.*`，反之亦然。
- 禁止 bodySmall 用于正文段落。
- 禁止普通列表/导航箭头使用陶土 `accent`（accent 仅用于学习行动/主 CTA；普通箭头用 `textTertiary` / `primary[700]`，教材域用 `inkFaint`）。
- 禁止统计数字使用 serif 字体导致 0 与 O 混淆（统计数字用 `FontFamily.sans` + `fontVariant: ['tabular-nums']`）。
- 禁止 Tab 根页显示 back 按钮。
- 禁止病例/症状卡片每个使用不同彩色 icon 背景（统一 `primary[50]`，仅状态色用语义色）。
- 禁止硬编码颜色、字号、行高、间距、圆角、阴影，必须引用 `Colors` / `Typography` / `Spacing` / `BorderRadius` / `Layout` / `Shadows` token。
- 禁止在组件内根据文档自行创造 token（如 `Colors.primary[700]`、`Spacing.xxx`、`Typography.xxx`），文档中出现的 token 必须在 `constants/*` 中真实存在。

## 11. 评审清单

每次 UI 调整依次检查：

1. **功能性**：信息是否更容易找到和操作。
2. **状态完整性**：空/错/加载状态是否遵循规则，有无编造数据。
3. **字族分层**：内容层 serif、操作层 sans 是否正确区分，token 是否显式组合 `FontFamily.*` + `Typography.*`。
4. **细节执行**：间距、对齐、字号、行高、点击区域是否统一。
5. **视觉层级**：用户是否能一眼看到当前最重要的信息；Hero 是否唯一。
6. **卡片/分隔线**：是否该用卡片的地方用了卡片，该用分隔线的地方没套卡片。
7. **禁止模式**：对照第 10 节反例清单逐项核查。
8. **哲学一致性**：是否符合临床编辑式学习体验。

## 12. 实现门禁

UI 实现必须满足：

1. 不硬编码颜色、字号、行高、间距、圆角、阴影，必须引用 token。
2. 不新增临时视觉 token，除非同步更新 `constants/*` 与本文件。
3. 每次 UI 修改后，必须对照第 11 节评审清单。
4. 若组件违反第 10 节禁止模式，必须先修正再提交。
5. 若发现文档与 token 代码冲突，必须记录为 design-token drift，不得静默选择一方。

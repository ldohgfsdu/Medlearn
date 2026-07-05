# Obsidian 与文档同步

MedLearn 用三套 Obsidian 空间 + 一个 Git 仓库，避免「三份文档各写各的」。

## Agent 接手清单（别的 agent 先看这段）

### 权威来源（按优先级）

1. **代码与测试** — 行为以 `app/`、`services/`、`supabase/` 为准
2. **`docs/CURRENT_STATE.md`** — 当前执行状态（生成物，勿手改）
3. **`site/`** — 对外文档站源文件（VitePress）
4. **`docs/`** — 内部工程文档（ADR、管线、API）
5. **`F:\MedLearn Vault\Medlearn\`** — 人类笔记与草稿，**不是**产品事实源

### Agent 应该怎么改文档

**直接改仓库里的文件**，不要打开 Obsidian：

```text
改 FAQ        →  F:\ml\site\faq.md
改侧栏/导航   →  F:\ml\site\.vitepress\config.mts  →  npm run docs:obsidian:nav
改工程文档    →  F:\ml\docs\*.md
预览文档站    →  npm run docs:dev
构建文档站    →  npm run docs:build
```

改完在 `F:\ml` 提交 `site/` 或 `docs/`；用户 `git push` 即同步 GitHub。

### 关键脚本（仓库内）

| 命令 | 作用 |
|------|------|
| `npm run docs:obsidian` | 修复 Vault 联接 + 重新生成 Obsidian 导航 |
| `npm run docs:obsidian:nav` | 只根据 `config.mts` 更新导航页 |
| `scripts/setup-obsidian-links.ps1` | 创建 `Medlearn/.site`、`Medlearn/.docs` 联接 |
| `scripts/generate-obsidian-doc-nav.mjs` | 写 Vault 内 `目录.md`、`发布文档站.md` |

### 禁止事项（避免再次踩坑）

- **不要**在 Vault 根目录或 `Medlearn/` 下创建**中文名联接**（Windows + Obsidian 会乱码）
- **不要**手改 `F:\MedLearn Vault\Medlearn\10 发布文档\目录.md` 等带 `authority: generated` 的文件
- **不要**在 `docs-site/` 写文档（遗留目录）；只用 `site/`
- **不要**把 Vault 笔记当已发布医学结论或当前状态

### 人类用户 vs Agent

| 角色 | 入口 |
|------|------|
| 用户（Obsidian） | `F:\MedLearn Vault` → `Medlearn/10 发布文档/目录` → 点链接 |
| Agent | 直接编辑 `F:\ml\site/`、`F:\ml\docs/` |

两边改的是**同一份文件**（用户经 `.site` / `.docs` 联接访问）。

### 接手后自检

```powershell
cd F:\ml
npm run docs:obsidian          # 联接与导航完好
npm run docs:build             # 文档站能构建
```

Vault 内应只有：`10 发布文档/`、`11 工程文档/`（中文普通文件夹），以及隐藏的 `.site/`、`.docs/` 联接。

## 三个 Vault

| Vault | 路径 | 角色 | Git |
|-------|------|------|-----|
| **MedLearn Vault** | `F:\MedLearn Vault` | 项目笔记 + 中文导航 + 隐藏联接 | `Medlearn/10 发布文档/目录.md` 点链编辑；实文件在隐藏的 `Medlearn/.site/`、`.docs/` |
| **私人 Vault** | `C:\Users\M1racle\Documents\Obsidian Vault` | 日记、个人思考 | 独立 |
| **仓库（权威）** | `F:\ml` | 代码、`site/` 文档站、`docs/` 工程文档 | `github.com/ldohgfsdu/medlearn` |

## 单一事实来源

| 内容 | 权威路径 | 发布形态 |
|------|----------|----------|
| 对外文档站 | `site/` | VitePress（`npm run docs:build`） |
| 内部工程文档 | `docs/` | 仓库内 Markdown |
| 执行状态 | `state/*.yaml` → `docs/CURRENT_STATE.md` | 生成物，勿手改 CURRENT_STATE |
| Vault 内 `Medlearn/` 笔记 | `F:\MedLearn Vault\Medlearn\` | 解释、草稿、验收记录；**不是**产品数据源 |

## 一次性设置

在 `F:\ml` 仓库根目录：

```powershell
npm run docs:obsidian
```

该命令会：

1. 创建 ASCII 联接 `Medlearn/.site` → `F:\ml\site`、`Medlearn/.docs` → `F:\ml\docs`（在文件树隐藏）
2. 创建中文普通文件夹 `10 发布文档/`、`11 工程文档/`，内含自动生成的 `目录.md`
3. 从 VitePress 配置生成导航链接（指向 `.site` / `.docs`）

> Windows 上**中文联接名**在 Obsidian 会乱码，因此用「中文目录 + 隐藏英文联接」方案。

打开 **`F:\MedLearn Vault`** → `Medlearn` → **`10 发布文档/目录`**。

## 日常编辑流程

### 改对外文档（文档网站）

1. 打开 `Medlearn/10 发布文档/目录.md`，点链接进入要改的页面（实文件在 `.site/`，与 `site/` 同一文件）
2. 本地预览：`npm run docs:dev`
3. 提交到 GitHub：

```powershell
cd F:\ml
git add site/
git commit -m "docs: ..."
git push
```

4. 需要静态站产物时：`npm run docs:build`（输出在 `site/.vitepress/dist/`）

### 改工程文档

1. 打开 `Medlearn/11 工程文档/目录.md`，点链接编辑（实文件在 `.docs/`）
2. 提交：

```powershell
git add docs/
git commit -m "docs: ..."
git push
```

### 改 Vault 内项目笔记

编辑 `Medlearn/` 下笔记（ADR 草稿、管线复盘等）。若用 Obsidian Git 插件，在 Vault 内提交；**不要**把整份 Vault 当成 `F:\ml` 的替代品。

## 导航同步

`Medlearn/00 导航/发布文档站.md` 由脚本自动生成，与 VitePress 顶栏/侧栏一致。

修改 `site/.vitepress/config.mts` 后运行：

```powershell
npm run docs:obsidian:nav
```

## 忽略构建产物

`Medlearn/.site/`、`Medlearn/.docs/` 在 Obsidian 文件树中已隐藏；构建缓存亦已忽略。

## 与私人 Vault 的边界

私人 Vault 的 `首页.md` 仅放个人笔记。MedLearn 正式资料请用 **MedLearn Vault** 的 `Medlearn/10 发布文档/`、`Medlearn/11 工程文档/` 或 `Medlearn/01`~`09` 项目笔记。
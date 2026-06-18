# 项目目录规范

本文件说明 `F:\ml` 中各目录的职责。根目录只保留源码入口、配置、
权威文档入口和少量必须由工具识别的运行目录。

## 核心源码

| 目录 | 用途 |
|---|---|
| `app/` | Expo Router 页面 |
| `components/` | 共享 UI |
| `hooks/` | 客户端状态与查询 hooks |
| `services/` | 客户端业务逻辑 |
| `shared/`、`utils/`、`lib/` | 可复用确定性逻辑 |
| `supabase/` | 数据库迁移和 Edge Functions |
| `scripts/` | 数据管道、验证、训练与运维脚本 |
| `tests/` | TypeScript、JavaScript 和 Python 回归测试 |

## 项目事实

| 目录/文件 | 用途 |
|---|---|
| `docs/` | 当前权威文档和历史文档归档 |
| `docs/adr/` | 所有 ADR 正文 |
| `state/` | 机器可读执行状态 |
| `manifests/` | 教材与数据范围清单 |
| `checklists/` | 验收和无回归清单 |
| `CONTEXT.md` | 领域术语 |
| `MEMORY.md` | 用户协作偏好 |

## 模型与教材

| 目录 | 用途 |
|---|---|
| `training/` | 数据集、评估、报告、checkpoint 和导出模型 |
| `textbook/` | 本地教材 PDF，不提交 Git |
| `.models/` | Hugging Face/ModelScope 模型缓存 |
| `.ollama/` | Ollama 本地模型 |
| `.venv-sft/` | Python 训练和管道环境 |

## 输出与历史

| 目录 | 用途 |
|---|---|
| `artifacts/` | 自动生成的分析、benchmark、管道输出和 QA 截图 |
| `generated/` | 教材解析生成物 |
| `tmp/` | 可随时重建的临时文件 |
| `reports/` | 需要长期保留的人工审计或汇总报告 |
| `archive/backups/` | 历史 UI、配置和手工备份，不参与构建 |
| `design-demos/` | 独立 HTML 设计原型 |

`artifacts/`、`generated/`、`tmp/`、本地模型和虚拟环境均不应作为当前
需求或项目状态的事实来源。

`.hermes-agent/`、`agent-tools/`、`terminals/` 等目录由本地 Agent 或终端
工具维护。它们已被 Git 忽略，不应被业务代码依赖，也不应手工归档到
源码目录。

## 放置规则

1. 新的权威说明放入 `docs/`，过时说明放入 `docs/archive/`。
2. ADR 正文只放入 `docs/adr/`，并登记到 `docs/ADR_INDEX.yaml`。
3. 脚本生成的文件必须写入 `artifacts/`、`generated/`、`training/reports/`
   或明确的 `reports/` 子目录，不能散落到根目录。
4. 历史源码快照放入 `archive/backups/`，不能被生产代码 import。
5. 临时调试文件放入 `tmp/`，确认无长期价值后可直接重建。
6. 不要在根目录新增日期命名的备份目录。


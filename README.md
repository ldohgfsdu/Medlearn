# MedLearn

MedLearn 是面向医学生与低年资住院医师的医学学习应用。

> 书是基础。框架是核心。推理是终点。

📖 **[使用文档 →](site/)** | 📥 **[下载 APK](https://github.com/ldohgfsdu/Medlearn/releases/latest)**

---

产品包含两项平级且完全独立的核心能力：

- **Knowledge**：搜索、浏览和复习结构化教材知识。
- **Case Simulator**：把已经掌握的理论知识应用到临床情境，训练信息收集、证据整合、诊断与处理判断。

用户可以直接进入任一能力。Knowledge 不是开始病例的前置步骤，Case Simulator 也不会解锁 Knowledge。病例完成后可以提供与薄弱点相关的可选知识链接，但不建立强制顺序或完成依赖。

> MedLearn 仅用于医学教育，不提供真实患者的诊断、治疗或临床决策支持。请勿输入任何可识别的真实患者信息。

## Current Status

项目处于 MVP 验证阶段，尚不是面向真实临床使用的产品。执行状态以 [`state/*.yaml`](state/) 和自动生成的 [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) 为准；不要从旧 PRD、历史审查报告或代码存在与否推断当前优先级。

### Active Object: Phase 1 Document Tree Golden Path

证明本地已通过的 EV1 教材知识能在 App 中作为结构化电子教材被消费（而不只是从数据库查询），以**支气管哮喘**和**肺结核**两个章节作为 golden path 验证段，跑通 `Document Tree → section → evidence/node → page-image return` 链路后再进行全量远端 EV1 上传。

| 子项 | 状态 | 说明 |
|---|---|---|
| 哮喘结构树渲染 | ✅ 代码完成 | 4 层 hierarchy 稳定，evidence_only 折叠进主题组，gate L169 禁项已解除 |
| 肺结核结构树渲染 | ✅ 闭环 | Web 实测四层分类树展开正常，p.107/p.109 原文 fallback 正常，51/51 测试通过 |
| 哮喘页图回跳（PageViewer） | ✅ 代码完成 | 275 引用 / 238 唯一 locator / 缺失 0，硬编码 `281` 已修复 |
| 哮喘 P0 叠图签字 | ⏳ 待人工 | 需主人确认 BDT 框在 64.webp 上对齐 |
| 哮喘 APK 真机验收 | ⏳ 待人工 | 7 项 checklist 待真机手测 |
| 肺结核页图回跳 | 🔵 可选扩展 | 当前为结构树级 fallback，非硬门；待范围决策后扩展 page-image bundle |

### 已完成里程碑（近期）

- `knowledge_ingestion_convergence` — EV1 本地知识质量在上传前收敛（2026-06-25）
- `first_mobile_test_package` — 首个移动测试构建（2026-06-21）
- `mobile_ui_feedback_repair` — 修复首批移动反馈问题（2026-06-21）
- `wrong_question_review_queue_closure` — 错题复习队列闭环（2026-06-21）
- `respiratory_mvp_real_question_validation` — 用一道真实错题验证呼吸 MVP（2026-06-20）

完整列表见 [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) 的 Completed 段。

### 阻塞项

- `knowledge_remote_upload_validation` — 等待 Phase 1 golden path 验证通过后走 staged/canary 上传
- `remote_supabase_validation` — 远端 API E2E 已过，iOS/Android 真机走查待 Phase 1 完成后解冻

## Product Model

```text
L0 Knowledge
   ↓
L1 Understanding
   ↓
L2 Framework
   ↓
L3 Clinical Reasoning
```

这些层级描述学习能力，不是强制用户路径。

```text
Knowledge
  ├─ Search
  ├─ Catalog
  └─ Textbook-grounded detail

Case Simulator
  ├─ History, examination and tests
  ├─ Diagnosis and differential diagnosis
  ├─ Evidence and treatment decisions
  └─ Scoring, feedback and retry
```

## Technology

| Layer | Stack |
|---|---|
| Client | Expo SDK 56, React Native 0.85, React 19, TypeScript 6 |
| Routing | Expo Router |
| Data | TanStack Query, Supabase JS |
| Backend | Supabase Auth, PostgreSQL, RLS, Edge Functions |
| Search | PostgreSQL full-text search and pgvector |
| AI | OpenAI-compatible providers through Edge Functions |
| Textbook pipeline | Python 3.11, PyMuPDF, Docling, Ollama |
| Tests | Node Test Runner, Python unittest |

## Repository

```text
app/                    Expo Router screens
components/             Shared UI components
constants/              Theme and domain constants
hooks/                  Auth, queries and business hooks
services/               Client business services
shared/                 Shared deterministic logic
supabase/               Migrations, seeds and Edge Functions
scripts/                Textbook ingestion and validation
tests/                  Node and Python regression tests
state/                  Machine-readable execution state
docs/                   Current documentation and archive
training/               Local model datasets, evaluation and checkpoints
artifacts/              Generated reports, benchmarks and QA output (ignored)
archive/                Historical backups; never imported by production code
design-demos/           Standalone UI prototypes
```

完整目录规则见 [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md)。

## Local Setup

Requirements:

- Node.js 22.13.1 for the validated Windows workflow
- npm
- Python 3.11+ for the textbook pipeline
- A Supabase project
- Ollama when running local extraction or embeddings

Install and configure:

```powershell
npm install
Copy-Item .env.example .env
npm start
```

Minimum client configuration:

```dotenv
EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

Never expose `SUPABASE_SERVICE_ROLE_KEY`, `AI_API_KEY`, or other server secrets through an `EXPO_PUBLIC_` variable.

## Validation

```powershell
npm run check
npm run test:python
npm run check:full
python scripts/validate_project_state.py
python scripts/generate_current_state.py --check
```

Windows with Node 24 and Expo 56 may run out of memory during web export. The validated local path uses Node 22.13.1.

## Documentation

**使用文档（面向用户）：** [`site/`](site/) — 快速开始、功能指南、常见问题、下载入口。

**工程文档（面向开发者）：** [`docs/`](docs/)

Start here:

1. [`docs/PROJECT_CONSTITUTION.md`](docs/PROJECT_CONSTITUTION.md) defines stable product identity and decision rules.
2. [`docs/MVP_PRD_V2.md`](docs/MVP_PRD_V2.md) defines current MVP scope.
3. [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) reports current execution state.
4. [`docs/ADR_INDEX.yaml`](docs/ADR_INDEX.yaml) indexes applicable architectural decisions.
5. [`CONTEXT.md`](CONTEXT.md) defines canonical domain language.

See [`docs/README.md`](docs/README.md) for the maintained documentation index. Superseded plans and reports live in [`docs/archive/`](docs/archive/) and are not current sources of truth.

## Medical And Content Safety

- Textbooks and medically reviewed cases are the primary medical sources.
- Search navigates to grounded content; it does not generate open-ended medical answers.
- Case ground truth, scoring rubrics and reviewer fields remain server-side.
- AI patient output is checked for diagnosis leakage and unsafe advice.
- Automated tests do not replace qualified medical review.
- Model, prompt, rubric or case-content changes require relevant regression tests and medical sampling.

## License

This repository currently has no `LICENSE` file. Clarify software licensing and third-party textbook rights before public distribution or reuse.

# MedLearn

MedLearn 是面向医学生与低年资住院医师的医学学习应用：

> 书是基础。框架是核心。推理是终点。

产品包含两项平级且完全独立的核心能力：

- **Knowledge**：搜索、浏览和复习结构化教材知识。
- **Case Simulator**：把已经掌握的理论知识应用到临床情境，训练信息收集、证据整合、诊断与处理判断。

用户可以直接进入任一能力。Knowledge 不是开始病例的前置步骤，Case Simulator 也不会解锁 Knowledge。病例完成后可以提供与薄弱点相关的可选知识链接，但不建立强制顺序或完成依赖。

> MedLearn 仅用于医学教育，不提供真实患者的诊断、治疗或临床决策支持。请勿输入任何可识别的真实患者信息。

## Current Status

项目处于 MVP 验证阶段，尚不是面向真实临床使用的产品。执行状态以 [`state/*.yaml`](state/) 和自动生成的 [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) 为准；不要从旧 PRD、历史审查报告或代码存在与否推断当前优先级。

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
```

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

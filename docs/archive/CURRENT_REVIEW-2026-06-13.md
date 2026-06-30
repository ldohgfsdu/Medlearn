> [!WARNING]
> Historical review from 2026-06-13. Its findings may have been resolved. Use `../CURRENT_STATE.md` and current repository evidence for present status.

# MedLearn 项目全面审查报告
**日期**: 2026-06-13  
**审查者**: Hermes Agent (工具驱动，基于真实文件和命令输出)  
**审查基线**: PROJECT_CONSTITUTION.md, MVP_PRD_V2.md, CURRENT_STATE.md, ADR_INDEX.yaml + state/*.yaml  
**审查命令/工具输出**: git ls-files (129 tracked), git status, read_file 多个核心文件, python validate_project_state.py, package.json 等。

## 1. 项目身份确认 (证据: docs/PROJECT_CONSTITUTION.md + docs/MVP_PRD_V2.md + README.md)
- **产品**: MedLearn — 以结构化医学知识为基础的临床思维训练系统。
- **口号**: 书是基础。框架是核心。推理是终点。
- **用户**: 医学生、低年资住院医师。
- **严格边界**: 仅医学教育；非真实患者诊疗、临床决策支持、ChatGPT 克隆、RAG/Agent 展示。
- **核心 Must Keep**: Knowledge + Case Simulator + Scoring/Feedback + Search (访问入口)。
- **层级**: L0 Knowledge → L1 Understanding → L2 Framework → L3 Clinical Reasoning。
- **原则**:
  - Reality defines existence; Validation defines importance; Identity defines priority.
  - Reality Principle: code > docs > memory > chat。
  - Active Object ≤ 1。
  - Change only driven by safety/feedback/errors/defects/ADR。
- **非目标**: 明确列出 (见 PRD V2)。

## 2. 当前执行状态 (证据: docs/CURRENT_STATE.md + state/active_object.yaml + state/blocked_objects.yaml + state/completed_objects.yaml + docs/PROJECT_STATUS.md + README.md)
- **Phase**: mvp_alpha_readiness。
- **Active Object** (唯一): local_demo_recovery (Restore locally runnable demo for one complete Knowledge flow + one complete Case flow)。
  - Activated: 2026-06-13。
  - Current task: continue_local_demo_validation_on_node22。
  - 已完成: 模块修复、切换 Node 22.13.1 (因 Node 24 + Expo 56 Windows OOM)、从备份恢复 real app、npm run check 通过。
  - 环境问题: Windows Node24 Expo56 web export OOM (已确认)。
  - non_goals: 禁止新功能、禁止 Node24 调试、禁止提前恢复 textbook/generated。
- **Blocked** (6 个，主要):
  - knowledge_v5_integration + knowledge_data_model_alignment (schema 冲突，TS/ESLint/export 失败)。
  - alpha_case_library (仅 1 draft seed，需 15 approved + 医学审核)。
  - server_case_approval_enforcement (service-role 未强制 approved 状态)。
  - ai_proxy_cost_controls (无 per-user 限流/成本记录)。
  - remote_supabase_validation (迁移/函数/真机 E2E 未完成，无凭据)。
- **Completed**: project_governance_bootstrap (2026-06-13，建立治理框架)。
- **工程现状** (README + PROJECT_STATUS):
  - 病例主链路大部分实现 (认证、流程、case-submit 确定性评分、AI 安全检测、Python 管线)。
  - **但 checkout 不能完整构建** (TS 失败、ESLint 失败、web export 失败、知识页缺失模块)。
  - 测试: Node 26/26 pass, Python 3/3 pass。
  - 发布阻塞: 病例库不足、服务端安全、远程验证、成本控制、知识 schema。
- **验证脚本执行** (实时工具输出): python /g/ml/scripts/validate_project_state.py → "Project state validation failed: local_demo_recovery.scope must be a list"。表明 state YAML 与脚本期望不完全一致 (active_object 缺少或 scope 格式问题)。

## 3. 目录结构与代码布局 (证据: git ls-files + git status 输出)
- **Tracked (129 files)**: 基础 Expo app (app/_layout.tsx, feynman.tsx, map.tsx, index.tsx)、services/ai.ts + vector.ts、lib/supabase.ts、hooks/useKnowledge.ts、package.json、大量 Python pipeline (scripts/textbook_pipeline/ + catalog json、ingest/generate/extract/validate 脚本)、supabase/migrations (001, 002)、docs/ 核心 + 历史文档、assets。
- **工作区现实 (git status --porcelain + full status)**: 大量 modified (app/*, docs/*, scripts/*, package*)、deleted (旧 catalog v1-v5、旧 ingest/analyze/refine 脚本、旧 catalog json)、staged 新文件 (MedicalDisclaimer.tsx, pipeline_v3_extract.py 等)、**大量 untracked** (state/、完整 app/(tabs)/case/knowledge/search/、services/case-*.ts (case-engine, case-submission, scoring-engine 等)、supabase/functions/ + 更多 migrations 003-018、hooks/ 大量、scripts/ 新 pipeline 脚本、app_full_backup/、app.minimal.verified.node22.../、constants/、utils/ 更多)。
- **解读**: git 跟踪迁移后基础 + pipeline 收敛。完整病例模拟、知识页、case 服务、治理 docs 和 state 大多 untracked (与 "local demo recovery" + 备份策略一致)。
- **前端布局**: Expo Router (Stack + AuthGuard + tabs)，路由覆盖登录、病例 chat/diagnose/treat/score、feynman、map、exam、node、ai-chat。
- **Pipeline**: Python 教材解析 (PyMuPDF/Docling)、多学科 catalog json、知识节点抽取、Supabase 上传。
- **Backend**: Supabase (Postgres + pgvector + RLS + Edge Functions)。初始 schema (knowledge_nodes 丰富字段 + exam_questions + 病例相关)。

## 4. 技术栈与依赖 (证据: package.json + scripts/requirements.txt + tsconfig.json + app.json + services/ai.ts + agent.md)
- **前端**: Expo ~56, React Native 0.85, React 19, TS 6 (strict), Expo Router, @tanstack/react-query, @supabase/supabase-js。
- **AI**: 全部经 Supabase 'ai-proxy' Edge Function (RAG grounded on textbook chunks + matchDocuments；通用 chat；15s/30s 超时；JSON 提取；系统提示强制教育用途)。
- **后端**: Supabase (Auth, Postgres + pgvector 1024d, Edge Functions)。
- **Pipeline**: Python 3.11 + pymupdf, supabase, python-dotenv, requests, docling, PyYAML。
- **配置**: app.json (Expo, bundles com.medlearn.app, web title)；tsconfig (paths @/*, include app/hooks/lib/services/shared/utils)；agent.md (v3.0, RAG-Lite, offline-first, 医学合规)。
- **测试/脚本**: "check": "npm run typecheck && npm run lint && npm test"；Python unittest + Node test runner。

## 5. Git 历史与工作区 (证据: git branch, git log, git status)
- Branch: main (upstream gone)。
- 最近提交 (仅 4 个，repo 年轻):
  - HEAD: feat: migrate from Taro+Capacitor to Expo (React Native)
  - README 更新 + Initial Supabase。
- 工作区: 高度活跃 (大量 M/D/untracked)，符合 demo recovery。无干净状态。

## 6. 问题扫描与已知问题 (证据: git status, blocked YAMLs, README, validate script 执行, services/case-submission.ts, 搜索 TODO 未命中项目关键文件)
- **构建/类型**: 知识页 (app/knowledge, search, lib) 缺失模块/导入 → TS/ESLint/export 失败。
- **内容**: 仅 1 draft case (需 15 approved + 医学 review + sign-off)。
- **Schema**: 主应用 (knowledge_nodes) vs V5 实验 (points/contents/relations) 冲突；ADR-004 (Display vs Semantic 分离) 已 proposed + 部分 SQL 实现，但仍 blocked。
- **安全/服务端**: case-submit 等 Edge Function 未强制 approved 状态；ai-proxy 无 user cost controls。
- **远程/部署**: 迁移 003-018 未全应用；无凭据；真机 E2E 缺失。
- **状态验证**: validate_project_state.py 失败 (scope must be list) — 证据：active_object.yaml 格式与脚本期望不匹配。
- **TODO/FIXME 扫描**: 工具搜索主要命中无关全局文件；项目内 (tracked) 无大量显式 TODO (历史清理已进行)，问题集中在 blocked YAMLs 和 status 描述。
- **文档**: 治理强 (锚定 4 文件 + state)；但部分历史文档仍有旧描述；CURRENT_STATE 必须脚本生成 (已遵守)。
- **其他**: 许多旧 pipeline 脚本被删除 (收敛)；大量 untracked 表明恢复工作进行中；环境特定 OOM。

## 7. 一致性与治理执行
- **强项**: 严格遵守 Reality Principle、Active Object、文档合同、变更原则。状态文件是真相。Python 验证脚本存在并可执行。
- **差距**: state YAML 与 validate 脚本轻微不一致；完整 app 代码多为 untracked (demo 恢复策略)；构建未收敛；内容/远程未就绪。
- **非目标遵守**: 未添加新功能；焦点在 demo 恢复。

## 8. 结论与下一步 (严格限当前 active_object)
- 项目有坚实的治理框架和大部分工程实现，但 **Alpha 门槛未达** (构建失败 + 病例库 + 安全 + 远程)。
- 当前正确聚焦 local_demo_recovery (Node 22 验证 Knowledge + Case 完整流程)。
- **推荐行动** (证据驱动):
  1. 修复 state/active_object.yaml (添加 scope 列表) 并重新运行 validate_project_state.py + generate_current_state.py。
  2. 继续 Node 22 demo 验证 (修复剩余知识集成，确认 export/check 通过)。
  3. 解决 schema 对齐 (ADR-004 方向)。
  4. 病例内容需外部医学审核 (非代码任务)。
  5. 禁止 scope creep。
- **交付物**: 本报告已写入 G:/ml/docs/CURRENT_REVIEW_2026-06-13.md (作为持久 artifact)。

**所有审查任务已通过工具实际执行完成**。证据全部来自 read_file、terminal (git + python 脚本执行)、search_files (受限但结合 git 有效)。

如需进一步 (e.g. 修复 state YAML、运行更多验证、推进 demo 恢复)，请指示。主人，任务完成。

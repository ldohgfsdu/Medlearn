# 修复教材提取流程 + 应用数据库访问问题

## Context

教材提取 pipeline 存在 8 个 bug/设计缺陷，应用端存在 5 个数据库访问问题（含 1 个严重安全问题）。两类问题相互独立，可并行修复。

---

## Area 1: Python Pipeline 修复（8 项）

### Phase 1A: 独立 Bug 修复（可并行）

| # | 文件 | 修复内容 |
|---|------|---------|
| 1 | `scripts/textbook_pipeline/segment_by_catalog.py:87` | `_compute_page_ranges` 末尾加 `seg["pageEnd"] = max(seg["pageStart"], seg.get("pageEnd", seg["pageStart"]))` 防止 pageEnd < pageStart |
| 2 | `scripts/textbook_pipeline/extract_knowledge_nodes.py:149` | heading hash 加行索引 `f"{seg['segmentId']}:{idx}:{line}"`，防同 segment 重复 heading 产出重复 ID |
| 3 | `scripts/textbook_pipeline/upload_to_supabase.py:91` | `from textbook_pipeline.metadata import PIPELINE_VERSION`，替换硬编码 `"2.0.0"` fallback |
| 4 | `scripts/textbook_parser.py:329` | `except Exception: pass` → `except Exception as e: print(f"  Warning: failed to record pipeline run: {e}")` |
| 5 | `scripts/textbook_pipeline/segment_by_catalog.py:133,143,145` | 移除 `nodeCount` 字段（validator 自行计算，该字段永远为 1，误导） |

### Phase 1B: 依赖性修复

| # | 文件 | 修复内容 |
|---|------|---------|
| 6 | `scripts/textbook_pipeline/segment_by_catalog.py:61-62` | 层级匹配加守卫：`len(t_norm) >= 4`、`len(core_title) - len(t_norm) >= 4`，去掉 `or t_norm in core_title` 只保留 `startswith` |
| 7 | `scripts/textbook_parser.py:161-162, 189-190` | segment/nodes 缓存检查增加 mtime 比对：上游文件更新时自动失效 |
| 8 | `scripts/textbook_parser.py:159,168` | 缺 catalog / 缺 pages 分别打印明确的 warning 信息 |

---

## Area 2: 应用数据库访问修复（5 项）

### 发现的核心问题

应用端通过 Supabase client 访问数据库，存在以下问题：

1. **`useSubjects()` 拉全表去重** — `SELECT subject FROM knowledge_nodes` 返回所有行，JS 端 `new Set()` 去重
2. **streak 计算重复** — `useKnowledge.ts` 和 `profile.tsx` 各写了一份
3. **analytics / profile 用原始 useEffect** — 没有 React Query 缓存，每次 mount 重新请求
4. **case 流程 5 个页面重复拉同一行 case_sessions** — chat / diagnose / treat / score 各自独立 fetch
5. **QueryClient 无全局配置** — 默认 staleTime=0，每次 focus 都 refetch

### Phase 2A: 基础（先行）

| # | 文件 | 修复内容 |
|---|------|---------|
| 9 | `app/_layout.tsx:7` | `new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, retry: 2, refetchOnWindowFocus: false } } })` |
| 10 | 新建 `utils/calcStreak.ts` | 抽取 `calcStreak` 纯函数，`useKnowledge.ts` 和 `profile.tsx` 共用 |

### Phase 2B: Hook 迁移

| # | 文件 | 修复内容 |
|---|------|---------|
| 11 | 新建 `hooks/useCaseSession.ts` | 统一 case_sessions + case_templates(*) 查询，chat/diagnose/treat/score 共用 |
| 12 | 新建 `hooks/useAnalyticsStats.ts` + `hooks/useProfileStats.ts` | 将 analytics.tsx 和 profile.tsx 的 useEffect 逻辑迁为 React Query hook |
| 13 | `hooks/useKnowledge.ts:78-98` | `useSubjects` 改用 `.select('subject').in_('subject', ...)` 或保持现状（数据量不大时 client-side dedup 可接受） |

---

## 执行顺序

```
Phase 1A ──→ Phase 1B ──→ 验证 pipeline
    ↕ （并行）
Phase 2A ──→ Phase 2B ──→ tsc --noEmit 验证
```

## 验证方式

- **Pipeline**: 对 `catalog.internal-medicine.json` 执行 `python textbook_parser.py parse --force`，检查 segments.jsonl 无 pageEnd < pageStart、无重复 ID、无 nodeCount 字段
- **App**: `npx tsc --noEmit` + 手动导航各 tab 验证数据加载和缓存行为

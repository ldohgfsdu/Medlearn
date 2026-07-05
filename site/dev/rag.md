# 搜索与 RAG

## 知识搜索（App）

| 路径 | 数据源 | 说明 |
|------|--------|------|
| `/search` | Supabase `knowledge_nodes` | `ilike` 模糊匹配标题与子章节，需联网 |
| `/map` 目录过滤 | 本地 `ev1DisplayContracts` bundle | 离线按章节名浏览 |

语义检索（pgvector）用于 RAG 与 embedding 匹配，经 `embedding-proxy` 生成向量后查询 `document_chunks`。

## RAG 流程（费曼复述等）

实现见 `services/ai.ts` → `evaluateWithRAG`：

```text
用户复述 → embedding-proxy → matchDocuments(Top-K)
         → 注入教材段落 → ai-proxy → 评估反馈
```

Embedding 默认走 Ollama `bge-m3`（可在设置中配置）；云端路径经 `embedding-proxy` 转发。
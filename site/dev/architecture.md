# 技术架构

```
Expo/RN App → TanStack Query → Supabase Client
                                 ├─ PostgreSQL (FTS + pgvector)
                                 ├─ Edge Functions (AI proxy)
                                 └─ Auth + RLS
```

## 分层

| 层 | 技术 |
|----|------|
| 前端 | Expo SDK 56 + RN 0.85 + React 19 + TS |
| 后端 | Supabase PostgreSQL + Edge Functions |
| AI | OpenAI-compatible via Edge Functions |
| 管线 | Python 3.11 + PyMuPDF + Ollama（EV1 证据管线） |

## 数据流

教材浏览（当前 App 主路径）：

```
Textbook PDF → EV1 pipeline → display contract → ev1DisplayContracts.ts → Expo App
```

云端同步与其它功能：

```
Supabase（knowledge_nodes / chunks / 进度）↔ Expo App
```

两条路径并行；教材 bundle 以本地构建产物为准，详见 [教材管线](/dev/textbook-pipeline)。

## 安全

- RLS 行级安全
- 服务端密钥隔离
- AI 输出安全过滤

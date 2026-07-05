# API 接口

## Supabase 客户端

通过 `lib/supabase.ts` 封装层访问 PostgreSQL；业务层用 TanStack Query 管理缓存与重试。

## Edge Functions

部署在 `supabase/functions/`，经 `npm run deploy:remote` 发布：

| Function | 说明 |
|----------|------|
| `ai-proxy` | AI 对话代理（费曼评估、RAG 等），带速率限制 |
| `embedding-proxy` | 文本 embedding（Ollama bge-m3 或 SiliconFlow） |
| `case-patient` | 病例患者对话，含诊断泄露检查与安全过滤 |
| `case-submit` | 病例提交与评分（调用 `_shared/case-scoring.ts`） |
| `case-abandon` | 放弃/终止病例会话 |

> `app/ai-chat` 是客户端路由，不是 Edge Function 名称。

## 核心表

| 表 | 用途 |
|----|------|
| `knowledge_nodes` | 云端知识节点（疾病详情等路径） |
| `case_templates` / `case_sessions` / `case_messages` | 病例模板与会话 |
| `case_events` | 训练行为埋点 |
| `feynman_records` | 费曼复述记录 |
| `user_profiles` | 用户资料 |
| `disease_identities` | 疾病身份映射 |

Schema 详见 `supabase/migrations/`；完整接口说明见仓库内 `docs/API.md`。
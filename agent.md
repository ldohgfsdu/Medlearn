# AGENT.md - MedLearn 开发规则

**版本**: 3.0
**更新日期**: 2026-06-05
**项目**: MedLearn - AI 驱动的医学思维训练移动应用

---

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| **前端框架** | Expo + React Native | Android + iOS 双端 |
| **路由** | Expo Router | 文件系统路由 |
| **语言** | TypeScript 5.x（严格模式） | |
| **后端** | Supabase | PostgreSQL + Auth + Storage |
| **状态管理** | @tanstack/react-query | 数据缓存和同步 |
| **AI** | mimo-v2.5-pro API | 费曼复述评估 |
| **向量检索** | Supabase pgvector | RAG 语义搜索 |

---

## 核心架构决策

1. **RAG-Lite 评估**：所有 AI 评估必须基于 `document_chunks` 中的教材原文。调用逻辑参考 `services/ai.ts`。
2. **离线优先 (Offline-First)**：使用 `@tanstack/react-query` 进行数据管理。所有 `supabase` 查询需封装在自定义 Hooks 中，并配置合理的 `staleTime`。
3. **知识图谱导航**：利用 `knowledge_nodes` 的关联字段，在 UI 中展示"相关推荐"，并在 AI 对话中引入关联知识点的追问。

---

## 代码组织规范

- 页面文件放在 `app/`（Expo Router 文件系统路由）
- 通用组件放在 `components/`
- 服务层代码放在 `services/`
- Supabase 相关代码放在 `lib/`
- React Query Hooks 放在 `hooks/`
- 工具函数放在 `utils/`

---

## 环境变量

所有公开的环境变量必须以 `EXPO_PUBLIC_` 前缀命名，参考 `.env.example`。

---

## AI 调用规范

- 所有 AI 调用通过 `services/ai.ts` 封装
- API Key 从环境变量读取，禁止硬编码
- 实现超时处理：15秒提示、30秒超时

---

## 医学内容合规

- 所有 AI 生成内容必须展示"⚠️ AI 生成内容，不构成医学建议"标识
- 种子数据必须标注教材来源
- VINDICATE 框架定义统一从 `constants/vindicate.ts` 导出

---

## 数据安全

- 所有数据库查询通过 Row Level Security (RLS) 实现用户数据隔离
- API Key 加密存储在环境变量中
- 请求频率限制（每用户每分钟 ≤ 10 次）

---

## 参考文档

- [PRD 文档](docs/PRD.md)
- [技术架构文档](docs/TECHNICAL_ARCHITECTURE.md)
- [Supabase 文档](https://supabase.com/docs)
- [Expo 文档](https://docs.expo.dev)

---

## 更新记录

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-06-05 | 3.0 | 技术栈迁移：Taro + Capacitor → Expo (React Native) |
| 2026-06-03 | 2.0 | 技术栈确定：Taro 4 + Capacitor APK + Supabase |
| 2026-06-03 | 1.0 | 初始版本 |

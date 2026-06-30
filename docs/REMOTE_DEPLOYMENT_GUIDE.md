# 远端 Supabase 部署指南

本指南用于完成 `remote_supabase_validation` 的**服务端部分**。真机 E2E 见 [E2E_ACCEPTANCE_CHECKLIST.md](./E2E_ACCEPTANCE_CHECKLIST.md)。

## 前置条件

| 项目 | 要求 |
|------|------|
| Supabase 项目 | 已创建，Postgres 17 |
| Supabase CLI | 已安装并登录 |
| 本地 `.env` | 已填写 URL、anon key、service role key、AI 密钥 |
| Node.js | 20+（与本地开发一致） |

## 0. 预检（推荐先跑）

```powershell
npm run preflight:deploy
npm run audit:remote
```

## 1. 安装并配置 CLI

```powershell
npm install -g supabase
```

在 `.env` 添加 Personal Access Token（Dashboard → Account → Access Tokens）：

```env
SUPABASE_ACCESS_TOKEN=sbp_...
```

可选备用路径：若只有数据库连接串，可设置 `DATABASE_URL` 后执行：

```powershell
npm run build:remote-bootstrap
npm run apply:remote-sql
```

或把 `scripts/remote-bootstrap.sql` 粘贴到 Supabase SQL Editor 手动执行。

## 2. 关联远端项目

```powershell
cd F:\ml
supabase link --project-ref <your-project-ref>
```

`project-ref` 在 Supabase Dashboard → Project Settings → General。

## 3. 配置环境变量

```powershell
Copy-Item .env.example .env
# 编辑 .env，至少填写：
# EXPO_PUBLIC_SUPABASE_URL
# EXPO_PUBLIC_SUPABASE_ANON_KEY
# SUPABASE_URL
# SUPABASE_SERVICE_ROLE_KEY
# AI_API_KEY
# SILICONFLOW_KEY（若使用 embedding-proxy）
```

## 4. 一键部署

```powershell
.\scripts\deploy-remote-supabase.ps1
```

脚本会依次执行：

1. `supabase db push` — 应用迁移 001–019
2. `supabase db execute` — 写入 15 个 approved 病例种子
3. 部署 5 个 Edge Functions
4. `supabase secrets set --env-file .env`
5. `npm run verify:remote`
6. `npm run validate:cases`

### 可选参数

```powershell
# 预览命令，不实际执行
.\scripts\deploy-remote-supabase.ps1 -DryRun

# 跳过密钥（已在 Dashboard 手动配置时）
.\scripts\deploy-remote-supabase.ps1 -SkipSecrets

# 仅更新数据库，不重部署函数
.\scripts\deploy-remote-supabase.ps1 -SkipFunctions
```

## 5. 手动分步部署

若不想用脚本，可按顺序手动执行：

```powershell
supabase db push
supabase db execute --linked -f supabase/seeds/002_alpha_case_library.sql
supabase functions deploy ai-proxy --no-verify-jwt
supabase functions deploy embedding-proxy --no-verify-jwt
supabase functions deploy case-submit --no-verify-jwt
supabase functions deploy case-patient --no-verify-jwt
supabase functions deploy case-abandon --no-verify-jwt
supabase secrets set --env-file .env
npm run verify:remote
npm run validate:cases
```

## 6. 验证通过标准

`npm run verify:remote` 应输出：

- 5 张核心表可访问
- approved 病例 >= 15
- 3 个 RPC 可调用
- 5 个 Edge Function 非 404

`npm run validate:cases` 应输出：

```text
病例总数 15，已批准 15，错误 0，警告 0
```

## 7. 常见问题

### `db push` 报迁移冲突

远端若已有手工建表，先用 Dashboard SQL Editor 检查现有 schema，必要时在测试项目重建数据库再 push。

### Edge Function 返回 404

确认函数名与 `supabase/functions/<name>/` 目录一致，且 `supabase link` 指向正确项目。

### 病例数不足 15

重新生成并执行种子：

```powershell
npm run generate:case-seeds
supabase db execute --linked -f supabase/seeds/002_alpha_case_library.sql
```

### 密钥未生效

函数部署后需重新 `supabase secrets set`。Dashboard → Edge Functions → Secrets 可核对。

## 8. 完成后

服务端验收通过后，进入真机流程：

1. 打开 [E2E_ACCEPTANCE_CHECKLIST.md](./E2E_ACCEPTANCE_CHECKLIST.md)
2. 在 iOS 和 Android 各完成一遍病例训练
3. 记录评分是否可复现、成本事件是否写入 `case_events` / `ai_proxy_usage`

全部打勾后，可将 `state/blocked_objects.yaml` 中的 `remote_supabase_validation` 移入 `completed_objects.yaml`。

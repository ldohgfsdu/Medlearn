# 验证与测试

## 测试层级

| 层级 | 框架 / 入口 |
|------|------------|
| 类型检查 | TypeScript `tsc` |
| Lint | ESLint |
| 单元测试 | Node Test Runner（`npm test`） |
| Python 测试 | unittest（`npm run test:python`） |
| 路由检查 | `npm run check:routes` |
| 远程 E2E | `scripts/run-remote-e2e.mjs`（`npm run e2e:remote`） |
| EV1 质量审计 | `scripts/audit-ev1-knowledge-quality.mjs` |

## 运行

```powershell
npm run check          # 路由 + 类型 + lint + Node 测试
npm run test:python    # Python 管线测试
npm run check:full     # check + Python 管线测试
npm run e2e:remote     # 远程 Supabase 冒烟（需 .env）
```

教材 bundle 相关质量闸门见 [教材管线](/dev/textbook-pipeline#质量闸门当前口径)。
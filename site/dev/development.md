# 开发指南

## 常用命令

```powershell
npm start              # 启动开发服务器
npm run typecheck      # TypeScript 检查
npm run lint           # ESLint
npm test               # Node 测试
npm run test:python    # Python 管线测试
npm run check:full     # 完整检查
```

## 文档站点

```powershell
npm run docs:dev       # 文档开发
npm run docs:build     # 构建文档
npm run docs:preview   # 预览构建
npm run docs:obsidian  # Obsidian 联接 + 导航同步（见 docs/OBSIDIAN_VAULT.md）
```

在 Obsidian 打开 `Medlearn/10 发布文档/目录`，点链接编辑（实文件在隐藏的 `Medlearn/.site/` = `site/`）；提交 `F:\ml` 即同步 GitHub。

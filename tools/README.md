# Tools

开发辅助工具目录。这里的脚本和 UI 不参与 MedLearn 生产构建，也不被 `app/` 或 `scripts/` 引用。

| 子目录 | 用途 |
|---|---|
| `hermes-office-ui/` | Hermes Agent 办公室监控面板（读取 `F:\ml\.hermes-agent`） |

启动 Hermes 办公室：

```powershell
cd F:\ml\tools\hermes-office-ui
.\start-hermes-office.ps1
```

默认 `HERMES_HOME` 为 `F:\ml\.hermes-agent`，可通过环境变量覆盖。
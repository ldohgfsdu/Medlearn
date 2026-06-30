# Hermes 办公室

本地监控 Hermes Gateway 与平台事件的轻量 Web UI。

## 启动

```powershell
.\start-hermes-office.ps1
```

浏览器访问：`http://127.0.0.1:8787/hermes-office.html`

## 依赖

- Hermes Gateway 运行在 `127.0.0.1:8642`
- `F:\ml\.hermes-agent\logs\gateway.log` 可读

## 环境变量

| 变量 | 默认值 |
|---|---|
| `HERMES_HOME` | `F:\ml\.hermes-agent` |
| `HERMES_API` | `http://127.0.0.1:8642` |
| `OFFICE_PORT` | `8787` |
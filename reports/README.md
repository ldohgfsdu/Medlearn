# Reports

这里保存需要长期留存、可供人工审计的结果，例如数据合并审计和标准
golden set 汇总。

可重新生成的临时分析、运行日志和 benchmark 应写入 `artifacts/`，训练
阶段报告应写入 `training/reports/`。

| 子目录 | 用途 |
|---|---|
| `audits/` | 人工全面审查、验收记录 |
| `archive/` | 审计中间态（已 supersede 的版本） |

保留的最终态实体解析审计：`entity-resolution-audit.json`、`entity-resolution-audit-mvp-applied.json`。


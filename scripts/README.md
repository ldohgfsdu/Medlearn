# Scripts

脚本按职责区分：

- `textbook_pipeline/`: 教材解析和知识摄取实现
- `prompt_system/`: 提取提示词与评估
- `analysis/`: 误差分析工具
- 根目录生产入口：`ingest_knowledge.py`、`pipeline_v3_extract.py`
- 根目录训练入口：`train_*`、`build_sft_*`、`evaluate_*`
- 标记为 `DEPRECATED`、`DEMO ONLY` 或 `EXPERIMENTAL` 的脚本仅用于历史复现

自动输出统一写入 `artifacts/`、`generated/` 或 `training/`，不要在项目
根目录创建新的结果目录。


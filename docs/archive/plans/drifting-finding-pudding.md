# AutoEQ 系列修正工具 — 实施计划

## Context

用户有一批耳机的原始频响测量数据（GraphicEQ 格式，127 频点，20Hz-20kHz），
需要为每款耳机自动生成修正 EQ，输出 GraphicEQ + PEQ + 可视化图表。
目标曲线优先支持自定义/平直（0dB 线），后续可扩展 Harman 等标准曲线。

## 项目结构

```
Desktop/AutoEq/
├── autoeq/
│   ├── __init__.py
│   ├── parser.py          # 解析 GraphicEQ 格式
│   ├── target.py          # 目标曲线定义（平直/自定义/Harman）
│   ├── correct.py         # 计算修正曲线 = 目标 - 测量
│   ├── peq.py             # 修正曲线 → 10段 PEQ 参数拟合
│   ├── export.py          # 输出 GraphicEQ / PEQ txt
│   └── visualize.py       # matplotlib 频响对比图
├── data/                  # 原始测量文件（现有）
├── output/                # 生成的修正文件 + 图表
├── cli.py                 # 命令行入口
├── run_batch.py           # 批量处理所有 data/ 下文件
└── requirements.txt       # numpy, scipy, matplotlib
```

## 数据流

```
测量文件 (GraphicEQ)
    │
    ▼
parser.parse()  →  {freq: np.array, gain: np.array}
    │
    ▼
target.generate(flat/custom)  →  {freq, target_gain}
    │
    ▼
correct.compute(measurement, target)  →  correction curve
    │
    ├──► export.to_graphiceq(correction)  →  .txt (EqualizerAPO)
    ├──► peq.fit(correction)              →  .txt (10段 PEQ 参数)
    └──► visualize.plot(measurement, target, correction)  →  .png
```

## 各模块要点

### 1. parser.py — 输入
- 解析 `GraphicEQ: f1 g1; f2 g2; ...` 字符串
- 返回 `(freqs: np.ndarray, gains: np.ndarray)`，shape (127,)
- 自动提取文件名中的耳机型号作为输出前缀

### 2. target.py — 目标曲线
- `flat(freqs)`: 全频段 0dB
- `custom(freqs, boost_params)`: 自定义低频抬升/高频衰减参数
- 预留 `harman_2018(freqs)` 接口

### 3. correct.py — 修正计算
- `correction = target_gain - measured_gain`
- 可选：smoothing（1/N octave 平滑，避免修正过于激进）
- 可选：gain 限幅（默认 ±12dB，防止极端修正）

### 4. peq.py — PEQ 拟合（核心难点）
- 输入：127 点修正曲线
- 输出：最多 10 个 PEQ 频段 `(type, freq, gain, Q)`
- 方法：使用 `scipy.optimize` 迭代拟合
- 支持的滤波器类型：PK（Peaking）、LS（Low Shelf）、HS（High Shelf）
- 输出格式兼容 Wavelet / Poweramp Equalizer

### 5. export.py — 输出
- `to_graphiceq()`: 127 段格式，与输入格式一致
- `to_peq_txt()`: 10 段 PEQ，人类可读的文本格式
- `to_peq_wavelet()`: Wavelet AutoEq 导入格式

### 6. visualize.py — 图表
- 三条曲线叠加：原始频响、目标曲线、修正后频响（= 原始 + 修正）
- 保存为 PNG，命名与耳机型号对应

## 实现顺序

1. parser.py + target.py（基础 IO，先跑通数据流）
2. correct.py（核心计算）
3. export.py（GraphicEQ 输出）
4. cli.py + run_batch.py（端到端可用）
5. visualize.py（图表）
6. peq.py（PEQ 拟合，最复杂的模块）
7. GitHub 发布准备

## GitHub 发布

```
Desktop/AutoEq/
├── .gitignore              # __pycache__, .venv, output/, *.png
├── README.md               # 项目说明 + 使用示例（中英双语）
├── LICENSE                 # MIT
├── pyproject.toml          # 项目元数据 + 依赖声明
├── data/                   # 测量示例（不包含用户私人数据）
└── examples/               # 示例输出
```

- 初始化 git 仓库，关联 GitHub remote
- README 包含：简介、安装方式、CLI 用法、输出示例截图
- `pyproject.toml` 声明项目名、版本、依赖（numpy, scipy, matplotlib）

## 验证方式

- 取一个测量文件，跑完整流程，检查输出的 GraphicEQ 是否等于目标 - 测量
- `run_batch.py` 批量处理全部 8 个文件，确认 output/ 下文件齐全
- 肉眼检查生成的频响对比图，确认修正方向正确
- `pip install -e .` 可正常安装，`python -m autoeq --help` 可用

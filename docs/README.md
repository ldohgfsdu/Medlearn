# MedLearn 项目文档

**项目名称**：MedLearn - AI 驱动的医学思维训练微信小程序  
**文档版本**：1.0  
**最后更新**：2026-06-03

---

## 项目简介

MedLearn 是一款 AI 驱动的医学思维训练微信小程序，帮助医学生和规培医生通过**费曼学习法**和 **VINDICATE 鉴别诊断框架**建立系统化临床思维，而非死记硬背。

### 核心理念

> **致广大而尽精微，极高明而道中庸**

### 核心价值

> **教用户"怎么想"，不是"记什么"。**

---

## 文档目录

### 1. 产品文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **需求文档（PRD）** | 产品需求、功能规划、用户画像、优先级排序 | [PRD.md](./PRD.md) |

### 2. 技术文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **技术架构文档** | 前后端架构、数据模型、分包策略 | [TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md) |
| **后端接口文档** | 云函数、云数据库、AI 服务接口 | [API.md](./API.md) |

### 3. 工具文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **PDF 提取方案** | 教材 PDF 提取流程、脚本使用指南 | [PDF_EXTRACTION_GUIDE.md](./PDF_EXTRACTION_GUIDE.md) |

---

## 功能规划

### P0 核心功能（V1.0）

| 功能 | 说明 | 状态 |
|------|------|------|
| 知识地图 | 三明治结构展示 800+ 知识点 | ✅ 已完成 |
| 费曼复述 | AI 四维度评估（准确性/完整性/清晰度/深度） | ✅ 已完成 |
| 苏格拉底对话 | AI 引导式提问，深化理解 | ✅ 已完成 |
| VINDICATE 鉴别诊断 | 九维度系统分析框架 | ✅ 已完成 |
| 病例沙盒 | 6 阶段临床模拟训练 | ✅ 已完成 |
| 间隔重复 | SM-2 算法动态调整复习计划 | ✅ 已完成 |
| 微信登录 | 一键登录，获取用户信息 | ✅ 已完成 |
| 医学内容合规 | AI 输出标识、免责声明 | ✅ 已完成 |

### P1 增强功能（V1.5）

| 功能 | 说明 | 状态 |
|------|------|------|
| 模拟考试 | 与费曼复述打通的学习闭环 | 🔄 开发中 |
| 语音输入 | 微信同声传译插件 | 📋 计划中 |
| 疾病对比 | AI 多维度对比分析 | 📋 计划中 |
| 推导链 | 4-6 步临床推理训练 | 📋 计划中 |
| 学习仪表盘 | 学习数据可视化 | 📋 计划中 |

### P2 扩展功能（V2.0）

| 功能 | 说明 | 状态 |
|------|------|------|
| AI 生成病例 | 根据薄弱点动态生成 | 📋 计划中 |
| AI 生成推导链 | 动态生成推理链 | 📋 计划中 |
| 学习日历 | 日历视图展示学习活动 | 📋 计划中 |
| 学习计划 | 个性化学习目标 | 📋 计划中 |
| 社交分享 | 学习成果分享 | 📋 计划中 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端框架 | Taro 4 + React 18 + TypeScript |
| 运行平台 | 微信小程序（基础库 ≥ 2.11.0） |
| 后端 | 微信云开发（云数据库 + 云函数） |
| AI | Anthropic Claude / OpenAI 兼容接口 |
| 构建 | Webpack5 → `dist/`，主包 < 2MB |

---

## 项目结构

```
MedLearn/
├── docs/                          # 项目文档
│   ├── README.md                  # 本文件
│   ├── PRD.md                     # 需求文档
│   ├── TECHNICAL_ARCHITECTURE.md  # 技术架构文档
│   ├── API.md                     # 后端接口文档
│   └── PDF_EXTRACTION_GUIDE.md    # PDF 提取方案
│
├── mini-program/                  # 小程序源码
│   ├── src/                       # 源代码
│   ├── cloud/                     # 云函数
│   ├── config/                    # 配置文件
│   └── package.json
│
├── medlearn-extractor/            # PDF 提取工具（方案 A）
│   ├── run_all.py                 # 一键运行
│   ├── step1-6_*.py               # 提取步骤
│   └── output/                    # 输出目录
│
├── scripts/                       # 脚本工具
│   └── textbook_pipeline/         # 教材处理流水线（方案 B）
│
├── generated/                     # 生成的数据
│   └── textbook/                  # 教材提取结果
│
└── public/                        # 静态资源
    └── extracted-knowledge.json   # 提取的知识数据
```

---

## 快速开始

### 1. 小程序开发

```bash
cd mini-program
npm install
npm run dev:weapp
```

### 2. PDF 提取

```bash
cd medlearn-extractor
pip install -r requirements.txt
python run_all.py --pdf "内科学.pdf"
```

### 3. 查看文档

直接在编辑器中打开 `docs/` 目录下的 Markdown 文件。

---

## 相关资源

- **微信小程序文档**：https://developers.weixin.qq.com/miniprogram/dev/framework/
- **Taro 文档**：https://taro-docs.jd.com/
- **微信云开发文档**：https://developers.weixin.qq.com/miniprogram/dev/wxcloud/basis/getting-started.html
- **VINDICATE 框架**：临床医学教学方法论，英联邦医学教育体系
- **费曼学习法**：Richard Feynman 提出的学习方法

---

## 联系方式

如有问题或建议，请联系开发团队。

---

*文档结束。本文档为 MedLearn 项目的总览文档，详细内容请查看各子文档。*

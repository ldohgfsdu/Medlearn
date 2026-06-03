"""Prompt templates for MedLearn knowledge extraction."""

PARSE_TOC_PROMPT = """你是一位医学教材目录解析专家。请从以下《内科学》教材目录文本中提取完整的章节结构，并为每个知识点标注其在教材中的起始页码。

要求：
1. 识别所有系统（如呼吸系统、循环系统、消化系统等）
2. 每个系统下识别所有章节
3. 每个章节下识别所有小节/知识点
4. 每个知识点标注类型：disease（疾病）、symptom（症状）、basic（基础理论）、syndrome（综合征）
5. 每个知识点标注 start_page（该知识点在教材中的起始页码，整数）
6. 严格输出 JSON，不要输出任何解释文字

输出格式：
{{
  "systems": [
    {{
      "name": "系统名称",
      "chapters": [
        {{
          "name": "章节名称",
          "sections": [
            {{
              "name": "小节/知识点名称",
              "type": "disease|symptom|basic|syndrome",
              "start_page": 10
            }}
          ]
        }}
      ]
    }}
  ]
}}

教材目录文本：
{text_content}
"""

STRUCTURIZE_PROMPT = """你是一位医学知识结构化专家。请将以下《内科学》教材原文转换为结构化的 JSON 格式。

知识点：{knowledge_name}
类型：{knowledge_type}

教材原文：
{text}

## 任务要求

### 1. 核心维度（必须覆盖）
从教材原文中提取以下9个维度的信息：
- definition（定义）：疾病的定义或概念
- etiology（病因）：导致疾病的病因或危险因素
- pathogenesis（发病机制）：疾病发生发展的机制
- pathology（病理）：病理改变或病理特征
- manifestation（临床表现）：症状、体征
- examination（辅助检查）：实验室检查、影像学检查等
- diagnosis（诊断标准）：诊断依据、鉴别诊断
- treatment（治疗）：治疗原则、药物、手术等
- prognosis（预后）：预后情况、并发症

### 2. 额外字段
- name（疾病名称）：从知识点名称提取，保留中文名称
- aliases（别名列表）：该疾病的其他名称，如缩写、英文名等，字符串数组
- keywords（关键词列表）：从原文提取≥5个核心关键词，字符串数组
- vindicate（鉴别诊断）：必须包含9个维度，每个维度写该知识点需要与哪些疾病鉴别
  - vascular（血管性）
  - infectious（感染性）
  - neoplastic（肿瘤性）
  - drug（药物性）
  - inflammatory（炎症性）
  - congenital（先天性）
  - autoimmune（自身免疫性）
  - traumatic（创伤性）
  - endocrine（内分泌性）

### 3. 处理规则
- 如果教材原文中有明确信息，必须忠实提取，保留专业术语
- 如果教材未详细展开某维度，填写"教材中未详细展开"
- 如果某维度完全不适用（如先天性疾病无创伤性鉴别），填写"不适用"
- 必须严格遵循输出格式，确保JSON格式正确

### 4. 输出格式
严格输出纯 JSON，不要输出任何解释文字或 markdown code block。

{{
  "name": "疾病名称",
  "aliases": ["别名"],
  "keywords": ["关键词"],
  "definition": "定义",
  "etiology": "病因",
  "pathogenesis": "发病机制",
  "pathology": "病理",
  "manifestation": "临床表现",
  "examination": "辅助检查",
  "diagnosis": "诊断",
  "treatment": "治疗",
  "prognosis": "预后",
  "vindicate": {{
    "vascular": "",
    "infectious": "",
    "neoplastic": "",
    "drug": "",
    "inflammatory": "",
    "congenital": "",
    "autoimmune": "",
    "traumatic": "",
    "endocrine": ""
  }}
}}
"""

CAUSAL_CHAIN_PROMPT = """你是一位医学逻辑分析专家。请为以下疾病生成因果推导链。

疾病：{knowledge_name}

结构化内容：
{text}

要求：
1. 从病因开始，逐步推导到临床表现
2. 每个环节说明机制
3. 适合用于医学教学和记忆
4. 严格输出 JSON 数组格式

输出格式：
[
  {{"step": 1, "cause": "...", "mechanism": "...", "result": "..."}},
  {{"step": 2, "cause": "...", "mechanism": "...", "result": "..."}}
]
"""

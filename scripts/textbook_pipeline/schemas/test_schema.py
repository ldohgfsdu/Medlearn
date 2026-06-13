"""Test / Examination schema definition for V4 pipeline."""

SCHEMA_NAME = "test"

REQUIRED_FIELDS = [
    "definition",
    "clinical_significance",
    "normal_range"
]

OPTIONAL_FIELDS = [
    "interpretation",
    "limitations",
    "related_diseases"
]

PROMPT_INSTRUCTIONS = """
这是一个检查或化验知识点。
只提取原文中明确出现的检查相关信息。
不要补充任何教材中未明确写出的内容。
每个字段必须包含 evidence_span。
不确定或未明确提到的字段必须设置 needs_review=true 并留空。
"""

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "definition": {"type": "object"},
        "clinical_significance": {"type": "object"},
        "normal_range": {"type": "object"},
        "interpretation": {"type": "object"},
        "limitations": {"type": "object"},
        "related_diseases": {"type": "object"}
    },
    "required": ["definition", "clinical_significance", "normal_range"]
}

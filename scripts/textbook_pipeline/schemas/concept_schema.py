"""General concept schema definition for V4 pipeline (fallback)."""

SCHEMA_NAME = "concept"

REQUIRED_FIELDS = [
    "definition",
    "clinical_relevance"
]

OPTIONAL_FIELDS = [
    "related_concepts",
    "examples",
    "notes"
]

PROMPT_INSTRUCTIONS = """
这是一个通用医学概念知识点。
只提取原文中明确出现的信息。
不要补充任何教材中未明确写出的内容。
每个字段必须包含 evidence_span。
不确定或未明确提到的字段必须设置 needs_review=true 并留空。
"""

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "definition": {"type": "object"},
        "clinical_relevance": {"type": "object"},
        "related_concepts": {"type": "object"},
        "examples": {"type": "object"},
        "notes": {"type": "object"}
    },
    "required": ["definition", "clinical_relevance"]
}

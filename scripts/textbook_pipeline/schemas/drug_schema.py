"""Drug schema definition for V4 pipeline."""

SCHEMA_NAME = "drug"

REQUIRED_FIELDS = [
    "definition",
    "indications",
    "mechanism_of_action"
]

OPTIONAL_FIELDS = [
    "pharmacokinetics",
    "adverse_reactions",
    "contraindications",
    "dosage"
]

PROMPT_INSTRUCTIONS = """
这是一个药物知识点。
只提取原文中明确出现的药物相关信息。
不要补充任何教材中未明确写出的内容。
每个字段必须包含 evidence_span。
不确定或未明确提到的字段必须设置 needs_review=true 并留空。
"""

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "definition": {"type": "object"},
        "indications": {"type": "object"},
        "mechanism_of_action": {"type": "object"},
        "pharmacokinetics": {"type": "object"},
        "adverse_reactions": {"type": "object"},
        "contraindications": {"type": "object"},
        "dosage": {"type": "object"}
    },
    "required": ["definition", "indications", "mechanism_of_action"]
}

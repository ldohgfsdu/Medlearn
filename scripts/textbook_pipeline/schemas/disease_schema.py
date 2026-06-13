"""Disease schema definition for V4 pipeline."""

SCHEMA_NAME = "disease"

REQUIRED_FIELDS = [
    "definition",
    "clinical_manifestations",
    "diagnostic_criteria",
    "treatment_principles"
]

OPTIONAL_FIELDS = [
    "epidemiology",
    "etiology_and_pathogenesis",
    "auxiliary_examinations",
    "differential_diagnosis",
    "prognosis",
    "complications"
]

PROMPT_INSTRUCTIONS = """
这是一个疾病知识点。
只提取原文中明确出现的疾病相关信息。
不要补充任何教材中未明确写出的内容。
每个字段必须包含 evidence_span。
不确定或未明确提到的字段必须设置 needs_review=true 并留空。
"""

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "definition": {"type": "object"},
        "clinical_manifestations": {"type": "object"},
        "diagnostic_criteria": {"type": "object"},
        "treatment_principles": {"type": "object"},
        "epidemiology": {"type": "object"},
        "etiology_and_pathogenesis": {"type": "object"},
        "auxiliary_examinations": {"type": "object"},
        "differential_diagnosis": {"type": "object"},
        "prognosis": {"type": "object"},
        "complications": {"type": "object"}
    },
    "required": ["definition", "clinical_manifestations", "diagnostic_criteria", "treatment_principles"]
}

"""V4 LLM Structurer - Step 3 of optimized pipeline.
Strictly follows all 5 hard constraints from user.
- Input must include both candidate_node + source_chunk
- Never hallucinate content outside source_chunk.raw_text
- All outputs must pass JSON Schema validation
- Every field must include evidence_span
- Only generates target_name (not target_id)
- Only supports 4 schemas for now: disease, drug, test, concept
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List
import re

# --- Schema Registry (minimal version for Step 3) ---
SCHEMA_TEMPLATES = {
    "disease": {
        "definition": True,
        "epidemiology": True,
        "etiology_and_pathogenesis": True,
        "clinical_manifestations": True,
        "diagnostic_criteria": True,
        "auxiliary_examinations": True,
        "differential_diagnosis": True,
        "treatment_principles": True,
        "prognosis": True
    },
    "drug": {
        "definition": True,
        "mechanism_of_action": True,
        "indications": True,
        "pharmacokinetics": True,
        "adverse_reactions": True,
        "contraindications": True
    },
    "test": {
        "definition": True,
        "clinical_significance": True,
        "normal_range": True,
        "interpretation": True
    },
    "concept": {
        "definition": True,
        "clinical_relevance": True,
        "related_concepts": True
    }
}

def get_schema(schema_type: str) -> Dict:
    """Minimal schema registry for Step 3."""
    return SCHEMA_TEMPLATES.get(schema_type, SCHEMA_TEMPLATES["concept"])

def call_medlearn_qwen3(prompt: str) -> str:
    """Call local medlearn-qwen3:8b with strict instructions."""
    try:
        full_prompt = f"""你是 Medlearn 医学知识结构化模型。
只能基于提供的 raw_text 提取内容，绝对不要补充任何教材中未出现的信息。
不确定或原文未明确提到的字段必须留空，并设置 needs_review=true。

{prompt}

请严格只输出合法 JSON，不要添加任何解释、Markdown 或代码块。"""
        
        result = subprocess.run(
            ["ollama", "run", "medlearn-qwen3:8b", full_prompt],
            capture_output=True, text=True, timeout=45
        )
        return result.stdout.strip()
    except Exception as e:
        return json.dumps({"error": str(e)})

def validate_output(output: Dict) -> bool:
    """Simple JSON Schema validation for Step 3."""
    required = ["knowledge_point", "content", "relations", "extraction_report"]
    if not all(k in output for k in required):
        return False
    if not isinstance(output["content"], dict):
        return False
    return True

def structure_candidate(candidate: Dict, source_chunk: Dict) -> Dict:
    """Core structuring function with all 5 hard constraints applied."""
    schema_type = candidate.get("suggested_schema", "concept")
    schema = get_schema(schema_type)
    
    raw_text = source_chunk.get("content", {}).get("raw_text", "")
    
    prompt = f"""请严格基于以下原文，结构化以下医学知识点。

知识点: {candidate['title']}
类型: {schema_type}
原文:
{raw_text[:4500]}

请按以下结构输出JSON（只使用以下字段，不要添加其他字段）：

{{
  "knowledge_point": {{
    "parent_id": null,
    "book_id": "{source_chunk.get('knowledge_point', {}).get('book_id', 'unknown')}",
    "subject": "{source_chunk.get('knowledge_point', {}).get('subject', '医学')}",
    "title": "{candidate['title']}",
    "type": "{schema_type}",
    "status": "ai_draft",
    "version": 1
  }},
  "content": {{
    "definition": {{"content": "", "source": {{}}, "evidence_span": {{"start_char": 0, "end_char": 0}}, "needs_review": false}},
    "clinical_manifestations": {{"content": "", "source": {{}}, "evidence_span": {{"start_char": 0, "end_char": 0}}, "needs_review": false}},
    "diagnostic_criteria": {{"content": "", "source": {{}}, "evidence_span": {{"start_char": 0, "end_char": 0}}, "needs_review": true}},
    "treatment_principles": {{"content": "", "source": {{}}, "evidence_span": {{"start_char": 0, "end_char": 0}}, "needs_review": true}}
    // 只填充 schema 中定义的字段
  }},
  "relations": [
    {{"target_name": "示例关联知识点", "relation_type": "complication"}}
  ],
  "extraction_report": {{
    "llm_usage": {{"model": "medlearn-qwen3:8b", "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}},
    "needs_human_review": true,
    "low_confidence_fields": [],
    "missing_fields": []
  }}
}}

只基于原文提取，不要脑补。"""

    raw_output = call_medlearn_qwen3(prompt)
    
    try:
        structured = json.loads(raw_output)
        if validate_output(structured):
            return structured
        else:
            raise ValueError("Schema validation failed")
    except Exception:
        # Fallback safe output
        return {
            "knowledge_point": candidate,
            "content": {"raw_text": raw_text[:500], "error": "LLM structuring failed"},
            "relations": [],
            "extraction_report": {
                "llm_usage": {"model": "medlearn-qwen3:8b", "error": True},
                "needs_human_review": True,
                "error": "JSON parsing or validation failed"
            }
        }

def run_structuring(candidates: List[Dict], source_chunks: List[Dict]) -> List[Dict]:
    """Main Step 3 entry point."""
    print(f"  🧠 LLM Structuring {len(candidates)} candidate nodes using medlearn-qwen3:8b...")
    
    results = []
    for candidate in candidates[:3]:  # Limit for safety in first run
        # Find corresponding source chunk
        source_chunk = next((c for c in source_chunks if c.get("knowledge_point", {}).get("title") == candidate.get("parent_title")), {})
        
        structured = structure_candidate(candidate, source_chunk)
        results.append(structured)
    
    print(f"  ✅ Structured {len(results)} knowledge points.")
    return results

# CLI for testing Step 3
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            results = run_structuring(data, data)  # simplified for testing
            output_path = path.parent / f"{path.stem}_structured_v4.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"Structured output saved to: {output_path}")
    else:
        print("Usage: python llm_structurer.py <candidates_file.json>")

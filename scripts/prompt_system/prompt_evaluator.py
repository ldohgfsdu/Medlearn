"""V4.5.1 Prompt Evaluator - Reliability Fix
Now uses deterministic matching:
Level 1: Exact Match
Level 2: Normalization + Synonym Map
No embedding or LLM judge in this version.
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple

class PromptEvaluator:
    def __init__(self):
        self.synonym_map = self._load_synonym_map()
        self.metrics = {}
    
    def _load_synonym_map(self) -> Dict[str, List[str]]:
        try:
            with open("evaluation_rules/synonym_map.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    
    def normalize_text(self, text: str) -> str:
        if not text:
            return ""
        t = text.lower().strip()
        t = ''.join(c for c in t if c.isalnum() or c in '()')
        return t
    
    def is_term_present(self, term: str, content: str) -> Tuple[bool, str]:
        """Level 1 + Level 2 matching with synonym support."""
        if not content or not term:
            return False, "no_content"
        
        term_norm = self.normalize_text(term)
        content_norm = self.normalize_text(content)
        
        # Level 1: Exact match
        if term.lower() in content.lower():
            return True, "exact"
        
        # Level 2: Normalized match
        if term_norm in content_norm:
            return True, "normalized"
        
        # Level 2: Synonym match
        synonyms = self.synonym_map.get(term, []) + self.synonym_map.get(term_norm, [])
        for syn in synonyms:
            if self.normalize_text(syn) in content_norm:
                return True, "synonym"
        
        return False, "not_found"
    
    def evaluate(self, structured_output: Dict, golden: Dict, source_text: str = "") -> Dict:
        """Detailed evaluation with match debug info."""
        content = structured_output.get("content", {})
        report = structured_output.get("extraction_report", {})
        
        evaluation = {
            "completeness": 0.0,
            "hallucination_risk": 0.0,
            "schema_compliance": 1.0 if not report.get("error") else 0.0,
            "relation_quality": 0.0,
            "match_details": []
        }
        
        must_have = golden.get("must_have_terms", [])
        filled_count = 0
        
        for term in must_have:
            found = False
            matched_text = None
            match_method = "not_found"
            
            for field_name, field in content.items():
                if isinstance(field, dict) and isinstance(field.get("content"), str):
                    present, method = self.is_term_present(term, field["content"])
                    if present:
                        found = True
                        matched_text = field["content"][:60] + "..."
                        match_method = method
                        filled_count += 1
                        break
            
            evaluation["match_details"].append({
                "term": term,
                "found": found,
                "match_method": match_method,
                "matched_text": matched_text
            })
            
            if not found:
                evaluation["match_details"][-1]["reason"] = "missing_in_output"
        
        # Completeness
        evaluation["completeness"] = round((filled_count / len(must_have)) * 100, 1) if must_have else 0.0
        
        # Hallucination (forbidden terms)
        forbidden = golden.get("forbidden_terms", [])
        hallucination_count = 0
        for term in forbidden:
            for field in content.values():
                if isinstance(field, dict) and isinstance(field.get("content"), str):
                    if term.lower() in field["content"].lower():
                        hallucination_count += 1
        evaluation["hallucination_risk"] = round(100 - (hallucination_count * 20), 1)
        
        # Relation Quality (simple)
        relations = structured_output.get("relations", [])
        evaluation["relation_quality"] = round(min(len(relations) / 3 * 100, 100), 1)
        
        # Overall (weighted)
        evaluation["overall_score"] = round(
            evaluation["completeness"] * 0.35 +
            evaluation["hallucination_risk"] * 0.30 +
            evaluation["schema_compliance"] * 0.20 +
            evaluation["relation_quality"] * 0.15,
            1
        )
        
        return evaluation

    def run_benchmark(self, outputs: List[Dict], golden_set: List[Dict]) -> Dict:
        """Run full benchmark."""
        scores = []
        for output, golden in zip(outputs, golden_set):
            score = self.evaluate(output, golden)
            scores.append(score)
        
        avg = {}
        for key in scores[0]:
            if isinstance(scores[0][key], (int, float)):
                avg[key] = round(sum(s[key] for s in scores) / len(scores), 1)
        
        print(f"\nBenchmark v4.5.1 (Evaluator Reliability Fix)")
        print(f"Overall Score: {avg.get('overall_score', 0)}%")
        print(f"Completeness : {avg.get('completeness', 0)}%")
        print(f"Hallucination: {avg.get('hallucination_risk', 0)}%")
        print(f"Schema       : {avg.get('schema_compliance', 0)}%")
        print(f"Relation     : {avg.get('relation_quality', 0)}%")
        
        return avg

if __name__ == "__main__":
    print("V4.5.1 Evaluator (with synonym normalization) loaded.")
    print("Use run_benchmark() to evaluate real outputs.")

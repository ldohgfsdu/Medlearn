"""V4 Extract Knowledge Nodes - Step 2 of optimized pipeline.
Strictly follows user constraints:
- Chunk ≠ KnowledgePoint
- Only identifies candidate knowledge nodes
- Does NOT fill diagnostic criteria, treatment, differential diagnosis etc.
- Prepares for deduplication with normalized_title and fingerprint
- Outputs only candidate list for llm_structurer.py (Step 3)
"""
from __future__ import annotations
import re
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any

# Medical knowledge point patterns (used for candidate identification only)
_MEDICAL_ENTITY_PATTERNS = [
    (r'(?:社区|医院|吸入|细菌|病毒|真菌|支原体)?获得性肺炎', "disease", "肺炎"),
    (r'慢性阻塞性肺疾病|慢阻肺|COPD', "disease", "慢性阻塞性肺疾病"),
    (r'心力衰竭|心衰', "disease", "心力衰竭"),
    (r'2型糖尿病|糖尿病', "disease", "2型糖尿病"),
    # Add more patterns as needed - keep focused on identification
]

def normalize_title(title: str) -> str:
    """Normalize title for deduplication."""
    if not title:
        return ""
    t = title.strip().lower()
    t = re.sub(r'[（(].*?[）)]', '', t)  # remove brackets
    t = re.sub(r'\s+', '', t)
    return t

def generate_fingerprint(book_id: str, normalized_title: str, node_type: str) -> str:
    """Generate unique fingerprint for deduplication."""
    key = f"{book_id}:{node_type}:{normalized_title}"
    return hashlib.md5(key.encode()).hexdigest()[:16]

def extract_candidate_nodes(chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Core function: One chunk → Multiple candidate knowledge nodes.
    Only identifies WHAT should be a node. Does NOT fill full content.
    """
    text = chunk.get("content", {}).get("raw_text", "")
    if not text or len(text) < 20:
        return []
    
    candidates = []
    book_id = chunk["knowledge_point"].get("book_id", "unknown")
    parent_title = chunk["knowledge_point"].get("title", "")
    
    # 1. Use heading and medical entity patterns to find candidates
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) > 80:  # too long is likely not a title
            continue
            
        for pattern, node_type, base_title in _MEDICAL_ENTITY_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                title = line[:60].strip()  # truncate long titles
                
                normalized = normalize_title(title)
                fingerprint = generate_fingerprint(book_id, normalized, node_type)
                
                candidate = {
                    "source_chunk_id": chunk.get("id") or f"chunk_{hashlib.md5(text[:100].encode()).hexdigest()[:8]}",
                    "title": title,
                    "type": node_type,
                    "aliases": [],  # Will be filled in Step 3 or manually
                    "parent_title": parent_title,
                    "source_span": {
                        "start_char": text.find(line),
                        "end_char": text.find(line) + len(line)
                    },
                    "reason": f"Matched medical entity pattern: {pattern}",
                    "confidence": 0.85,
                    "suggested_schema": node_type,
                    "normalized_title": normalized,
                    "fingerprint": fingerprint
                }
                candidates.append(candidate)
                break  # avoid duplicate matches
    
    # 2. Add section title as candidate if not already included
    if parent_title and not any(c["title"] == parent_title for c in candidates):
        normalized = normalize_title(parent_title)
        candidates.append({
            "source_chunk_id": chunk.get("id") or "root",
            "title": parent_title,
            "type": "section",
            "aliases": [],
            "parent_title": chunk["knowledge_point"].get("chapter", ""),
            "source_span": {"start_char": 0, "end_char": 100},
            "reason": "Section heading from parser",
            "confidence": 0.95,
            "suggested_schema": "section",
            "normalized_title": normalized,
            "fingerprint": generate_fingerprint(book_id, normalized, "section")
        })
    
    return candidates

def run_extract(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Main entry point for Step 2."""
    all_candidates = []
    
    print(f"  🔍 Extracting candidate knowledge nodes from {len(chunks)} chunks...")
    
    for chunk in chunks:
        candidates = extract_candidate_nodes(chunk)
        all_candidates.extend(candidates)
    
    print(f"  ✅ Extracted {len(all_candidates)} candidate knowledge nodes.")
    print("  Note: This step only identifies candidates. Full structuring happens in Step 3 (llm_structurer.py).")
    
    return all_candidates

# CLI for testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if input_path.exists():
            with open(input_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            candidates = run_extract(chunks)
            
            output_path = input_path.parent / f"{input_path.stem}_candidates.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(candidates, f, ensure_ascii=False, indent=2)
            print(f"Output written to: {output_path}")
    else:
        print("Usage: python extract_knowledge_nodes.py <chunks_file.json>")

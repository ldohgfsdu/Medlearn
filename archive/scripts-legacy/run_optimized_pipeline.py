#!/usr/bin/env python
"""
EXPERIMENTAL — not production. Use scripts/ingest_knowledge.py extract.
V4 batch structurer demo using basic PdfReader (not enhanced Docling reader).
"""
import sys
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from textbook_pipeline.readers.factory import read_file
from textbook_pipeline.llm_structurer import batch_structure

def main():
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = "textbook/生理学（第10版）.pdf"
    
    # Simple book_id mapping (fixed from textbook_identity.py)
    book_id = "physiology-10"
    if "内科学" in pdf_path or "internal-medicine" in str(pdf_path).lower():
        book_id = "internal-medicine-10"
    elif "生理学" in pdf_path:
        book_id = "physiology-10"
    elif "诊断学" in pdf_path:
        book_id = "diagnostics-10"
    
    out_dir = Path("artifacts/pipeline-output") / book_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🚀 Starting Medlearn V4 Optimized Pipeline for: {book_id}")
    print("=" * 70)
    
    # Stage 1: Enhanced PDF Reading
    print("\n📖 Stage 1: Reading PDF with improved parser...")
    result = read_file(str(pdf_path), book_id=book_id)
    print(f"   ✓ Successfully extracted {len(result.pages)} pages")
    print(f"   ✓ Total characters: {result.metadata.get('totalChars', 0)}")
    print(f"   ✓ TOC entries: {len(result.toc)}")
    
    # Stage 2: LLM-powered Structuring (Core Optimization)
    print("\n🧠 Stage 2: Structuring with local medlearn-qwen3:8b model...")
    structured_nodes = batch_structure(result.pages, book_id)
    
    # Stage 3: Save structured output for case generation
    output_file = out_dir / "structured_knowledge_nodes_v4.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "book_id": book_id,
            "pipeline_version": "v4-optimized",
            "total_nodes": len(structured_nodes),
            "nodes": structured_nodes
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 V4 Pipeline completed successfully!")
    print(f"   Output: {output_file}")
    print(f"   Generated {len(structured_nodes)} structured knowledge nodes")
    print("\nThese nodes are now ready for clinical case generation in Medlearn.")
    print("Local model (medlearn-qwen3:8b) was used for high-quality medical structuring.")

if __name__ == "__main__":
    main()

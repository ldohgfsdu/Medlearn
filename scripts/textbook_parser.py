"""V4.7.2 Textbook Parser - Single Active Object Mode.
Current Active Object: Influenza (流感)
Strictly follows single active object discipline.
"""
from __future__ import annotations
import json
import sys
import hashlib
from pathlib import Path
from textbook_pipeline.readers.factory import read_file
from textbook_pipeline.segment_by_catalog import run_segment
from textbook_pipeline.metadata import PIPELINE_VERSION

def create_v4_chunk(book_id: str, subject: str, chapter: str, title: str, text: str, chunk_type: str = "disease"):
    return {
        "id": f"chunk_{hashlib.md5(text[:100].encode()).hexdigest()[:12]}",
        "knowledge_point": {
            "parent_id": None,
            "book_id": book_id,
            "subject": subject,
            "chapter": chapter,
            "title": title,
            "type": chunk_type,
            "status": "ai_draft",
            "version": 1
        },
        "content": {
            "raw_text": text
        },
        "relations": [],
        "extraction_report": {
            "chunk_type": chunk_type,
            "raw_length": len(text),
            "pipeline_version": "v4.7.2",
            "suggested_schema": chunk_type
        }
    }

def main():
    disease = "流感"
    pdf_path = "textbook/内科学（第10版）.pdf"
    book_id = "internal-medicine-10"
    subject = "内科学"
    chapter = "呼吸系统疾病"
    
    print(f"\n🚀 V4.7.2 Parser - Active Object: {disease}")
    print("=" * 70)
    
    result = read_file(pdf_path, book_id=book_id)
    
    print(f"📑 Segmenting respiratory chapter for {disease}...")
    segments = run_segment(result)
    
    v4_chunks = []
    for segment in segments:
        if disease in segment.get("title", "") or "流感" in segment.get("text", ""):
            chunk = create_v4_chunk(
                book_id=book_id,
                subject=subject,
                chapter=chapter,
                title=segment.get("title", disease),
                text=segment.get("text", ""),
                chunk_type="disease"
            )
            v4_chunks.append(chunk)
    
    output_path = Path("output_v4") / f"influenza_chunks_v4.7.2.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(v4_chunks, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Parser completed for {disease}")
    print(f"Generated {len(v4_chunks)} chunks")
    print(f"Output: {output_path}")
    print("\nNext: extract_knowledge_nodes.py")

if __name__ == "__main__":
    main()

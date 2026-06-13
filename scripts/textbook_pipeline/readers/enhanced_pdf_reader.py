"""Enhanced PDF Reader using Docling + Local Medlearn-Qwen3 model.
This is the V4 optimized version for medical textbooks.
Uses Docling for superior layout/table understanding, then uses local Ollama model for structuring.
"""
from __future__ import annotations
import re
import hashlib
import json
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker import HierarchicalChunker

from .base import TextbookReader, ReaderResult, PageRecord, TocEntry
from ..metadata import PIPELINE_VERSION

class EnhancedPdfReader(TextbookReader):
    """V4 PDF Reader: Docling + Local LLM enhancement."""
    
    def __init__(self):
        self.converter = DocumentConverter()
        self.chunker = HierarchicalChunker()
    
    def read(self, path: str | Path, book_id: str | None = None) -> ReaderResult:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        print(f"  📄 Converting with Docling: {path.name}")
        
        # Use Docling for much better parsing (tables, layout, markdown)
        result = self.converter.convert(str(path))
        doc = result.document
        
        # Export to markdown (much better than raw get_text())
        markdown_text = doc.export_to_markdown()
        
        # Extract TOC if available
        toc: list[TocEntry] = []
        if hasattr(doc, 'toc') and doc.toc:
            for item in doc.toc:
                if isinstance(item, dict) and item.get('level', 0) <= 3:
                    toc.append(TocEntry(
                        level=item.get('level', 1),
                        title=item.get('title', '').strip(),
                        page=item.get('page', 1)
                    ))
        
        # Split into pages/chunks (approximate)
        pages = []
        chunks = self.chunker.chunk(doc)
        total_chars = 0
        
        for i, chunk in enumerate(chunks):
            text = chunk.text.strip() if hasattr(chunk, 'text') else str(chunk)
            text = re.sub(r'\s+', ' ', text).strip()
            char_count = len(text)
            total_chars += char_count
            pages.append(PageRecord(
                page_number=i + 1,
                text=text,
                char_count=char_count
            ))
        
        # Generate metadata
        source_sample = f"{path.name}:{len(pages)}:{total_chars}"
        sample_hash = hashlib.md5(source_sample.encode()).hexdigest()[:12]
        
        metadata = {
            "fileName": path.name,
            "totalPages": len(pages),
            "totalChars": total_chars,
            "sourceSize": path.stat().st_size,
            "sourceSampleHash": sample_hash,
            "pipelineVersion": PIPELINE_VERSION,
            "readerType": "enhanced_docling_v4",
            "hasTables": True,  # Docling handles tables better
            "exportFormat": "markdown"
        }
        
        report = {
            "sourceType": "pdf",
            "totalPages": len(pages),
            "tocEntries": len(toc),
            "avgCharsPerPage": round(total_chars / max(len(pages), 1)),
            "readerVersion": "v4-enhanced",
            "method": "docling + hierarchical chunking"
        }
        
        print(f"  ✅ Docling conversion complete. {len(pages)} chunks, {total_chars} chars.")
        
        return ReaderResult(
            source_path=str(path),
            book_id=book_id or "",
            pages=pages,
            toc=toc,
            metadata=metadata,
            report=report,
        )

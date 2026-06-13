"""V4 Supabase Writer - Step 6 of optimized pipeline.
Strictly follows all hard constraints:
- Uses upsert with unique constraint on (book_id, type, normalized_title)
- Fixed write order
- Creates pipeline_run_log
- All operations are small, retryable functions
- Failure of one item does not stop the batch
- Full summary at the end
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import supabase

class SupabaseWriter:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.client = supabase.create_client(supabase_url, supabase_key)
        self.run_id = str(uuid.uuid4())
        self.stats = {
            "total": 0,
            "written": 0,
            "failed": 0,
            "unresolved_relations": 0,
            "errors": []
        }
    
    def upsert_knowledge_point(self, kp: Dict) -> str | None:
        """Upsert with normalized_title for deduplication."""
        from textbook_pipeline.ingestion_contract import (
            DEPRECATION_NOTICE,
            KNOWLEDGE_POINTS_DEPRECATED,
        )

        if KNOWLEDGE_POINTS_DEPRECATED:
            raise RuntimeError(DEPRECATION_NOTICE)
        try:
            normalized = kp.get("normalized_title") or kp.get("title", "").lower().strip()
            
            data = {
                "id": kp.get("id") or str(uuid.uuid4()),
                "parent_id": kp.get("parent_id"),
                "book_id": kp.get("book_id"),
                "subject": kp.get("subject"),
                "title": kp.get("title"),
                "type": kp.get("type"),
                "status": kp.get("status", "ai_draft"),
                "version": kp.get("version", 1),
                "normalized_title": normalized,
                "aliases": kp.get("aliases", []),
                "metadata": kp.get("metadata", {})
            }
            
            result = self.client.table("knowledge_points").upsert(
                data, 
                on_conflict="book_id,type,normalized_title"
            ).execute()
            
            return data["id"]
        except Exception as e:
            self.stats["errors"].append(f"Point upsert failed: {str(e)}")
            return None
    
    def upsert_knowledge_content(self, point_id: str, content: Dict) -> bool:
        """Upsert content with search_vector placeholder."""
        try:
            data = {
                "knowledge_point_id": point_id,
                "content": content,
                "search_vector": "placeholder"  # Can be computed with tsvector later
            }
            self.client.table("knowledge_contents").upsert(data).execute()
            return True
        except Exception as e:
            self.stats["errors"].append(f"Content upsert failed for {point_id}: {str(e)}")
            return False
    
    def write_resolved_relation(self, relation: Dict) -> bool:
        """Write resolved relation."""
        try:
            if not relation.get("resolved_target_id"):
                return self.write_unresolved_relation(relation)
            
            data = {
                "source_id": relation["source_id"],
                "target_id": relation["resolved_target_id"],
                "relation_type": relation["relation_type"],
                "strength": relation.get("confidence", 0.8)
            }
            self.client.table("knowledge_relations").upsert(
                data, 
                on_conflict="source_id,target_id,relation_type"
            ).execute()
            return True
        except Exception as e:
            self.stats["errors"].append(f"Relation write failed: {str(e)}")
            return False
    
    def write_unresolved_relation(self, relation: Dict) -> bool:
        """Write to unresolved_relations table."""
        try:
            data = {
                "source_id": relation.get("source_id"),
                "target_name": relation.get("target_name"),
                "relation_type": relation.get("relation_type"),
                "candidates": relation.get("candidates", []),
                "reason": f"Match method: {relation.get('match_method')}, confidence: {relation.get('confidence')}"
            }
            self.client.table("unresolved_relations").insert(data).execute()
            self.stats["unresolved_relations"] += 1
            return True
        except Exception:
            return False
    
    def write_pipeline_log(self, input_file: str, total_chunks: int, total_candidates: int):
        """Write run summary log."""
        try:
            log = {
                "pipeline_version": "v4.1",
                "book_id": input_file,
                "input_file": input_file,
                "total_chunks": total_chunks,
                "total_candidates": total_candidates,
                "total_written": self.stats["written"],
                "total_failed": self.stats["failed"],
                "total_unresolved_relations": self.stats["unresolved_relations"],
                "llm_usage": {"note": "tracked per item in extraction_report"},
                "errors": self.stats["errors"]
            }
            self.client.table("pipeline_run_log").insert(log).execute()
            print(f"📊 Pipeline run logged. Written: {self.stats['written']}, Failed: {self.stats['failed']}")
        except Exception as e:
            print(f"Warning: Failed to write pipeline log: {e}")
    
    def write_structured_item(self, structured: Dict, all_points: List[Dict]) -> bool:
        """One complete structured item with error isolation."""
        try:
            kp = structured.get("knowledge_point", {})
            point_id = self.upsert_knowledge_point(kp)
            if not point_id:
                self.stats["failed"] += 1
                return False
            
            content_ok = self.upsert_knowledge_content(point_id, structured.get("content", {}))
            if not content_ok:
                self.stats["failed"] += 1
                return False
            
            for rel in structured.get("relations", []):
                if isinstance(rel, dict) and rel.get("target_name"):
                    rel["source_id"] = point_id
                    self.write_resolved_relation(rel)
            
            self.stats["written"] += 1
            return True
        except Exception as e:
            self.stats["errors"].append(f"Item failed: {str(e)}")
            self.stats["failed"] += 1
            return False
    
    def write_batch(self, structured_items: List[Dict], input_file: str = "unknown"):
        """Main batch writer with full isolation and logging."""
        print(f"\n💾 Starting Supabase write for {len(structured_items)} items...")
        
        all_points = []  # Can be populated from previous steps
        
        for item in structured_items:
            self.write_structured_item(item, all_points)
        
        self.write_pipeline_log(
            input_file=input_file,
            total_chunks=len(structured_items),
            total_candidates=len(structured_items)
        )
        
        print("\n" + "="*60)
        print("📈 FINAL SUMMARY")
        print(f"Total items     : {len(structured_items)}")
        print(f"Successfully written : {self.stats['written']}")
        print(f"Failed          : {self.stats['failed']}")
        print(f"Unresolved relations : {self.stats['unresolved_relations']}")
        print("="*60)
        
        return self.stats

# Create tables suggestion (run once)
TABLE_CREATION_SQL = """
-- Add normalized_title and unique constraint
ALTER TABLE knowledge_points ADD COLUMN IF NOT EXISTS normalized_title text;
ALTER TABLE knowledge_points ADD CONSTRAINT IF NOT EXISTS unique_book_type_title 
    UNIQUE (book_id, type, normalized_title);

-- Create unresolved_relations table
CREATE TABLE IF NOT EXISTS unresolved_relations (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id uuid NOT NULL REFERENCES knowledge_points(id),
    target_name text NOT NULL,
    relation_type text NOT NULL,
    candidates jsonb DEFAULT '[]'::jsonb,
    reason text,
    created_at timestamptz DEFAULT now()
);

-- Create pipeline_run_log table
CREATE TABLE IF NOT EXISTS pipeline_run_log (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_version text,
    book_id text,
    input_file text,
    total_chunks int,
    total_candidates int,
    total_written int,
    total_failed int,
    total_unresolved_relations int,
    llm_usage jsonb DEFAULT '{}',
    errors jsonb DEFAULT '[]',
    created_at timestamptz DEFAULT now()
);
"""

if __name__ == "__main__":
    print("Supabase Writer v4 ready.")
    print("Run TABLE_CREATION_SQL first in Supabase SQL editor.")
    print("Then use: writer = SupabaseWriter(url, key); writer.write_batch(items)")

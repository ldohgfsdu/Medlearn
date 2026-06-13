#!/usr/bin/env python3
"""
Stage 3A - Read-only Historical Data Audit Script (Strictly Read-Only)
This script ONLY performs SELECT queries. No writes, deletes, updates, or resets of any kind.

Usage:
  1. Ensure .env has SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY)
  2. python scripts/audit_stage3a_readonly.py > audit_stage3a_$(date +%Y%m%d_%H%M%S).log 2>&1

The script will:
- Attempt connection (read-only)
- Print source distribution for knowledge_nodes and document_chunks
- Calculate field missing rates
- Print per-textbook coverage
- Log exact SQL executed, timestamps, and raw results for auditability

All output is designed to be saved and reviewed.
"""
import os
import json
import datetime
from collections import defaultdict
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def log(msg):
    print(f"[{datetime.datetime.now().isoformat()}] {msg}")

def main():
    start = datetime.datetime.now().isoformat()
    log("=== Stage 3A Read-only Supabase Historical Data Audit START ===")
    log("MODE: READ-ONLY ONLY. No modifications will be performed.")
    log(f"Start time: {start}")

    url = os.environ.get("SUPABASE_URL") or os.environ.get("EXPO_PUBLIC_SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or 
           os.environ.get("SUPABASE_SERVICE_KEY"))

    if not url or not key:
        log("ERROR: Missing SUPABASE credentials in .env. Cannot connect.")
        log("Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and re-run.")
        log("This script performs ONLY SELECT queries when credentials are present.")
        return

    try:
        client = create_client(url, key)
        log("Connected to Supabase (read-only client created).")
    except Exception as e:
        log(f"ERROR creating Supabase client: {str(e)[:200]}")
        return

    # === knowledge_nodes audit ===
    log("\n--- knowledge_nodes audit ---")
    try:
        # Get a sample for local aggregation (PostgREST has limited GROUP BY in free tier)
        res = client.table("knowledge_nodes").select(
            "source, node_source, book_id, textbook, source_span"
        ).execute()

        total_kn = len(res.data)
        log(f"Sampled/returned rows for analysis: {total_kn} (full count may require SQL)")

        groups = defaultdict(int)
        missing_span = 0
        missing_evidence = 0
        missing_book = 0
        textbook_counts = defaultdict(int)

        for row in res.data:
            key = (
                row.get("source") or "NULL",
                row.get("node_source") or "NULL",
                row.get("book_id") or "NULL",
                row.get("textbook") or "NULL",
            )
            groups[key] += 1
            textbook_counts[row.get("textbook") or "NULL"] += 1

            ssp = row.get("source_span") or {}
            if not ssp:
                missing_span += 1
            if not ssp.get("evidence"):
                missing_evidence += 1
            if not row.get("book_id"):
                missing_book += 1

        log("Top source/node_source/book_id/textbook groups:")
        for (src, ns, bid, tb), cnt in sorted(groups.items(), key=lambda x: -x[1])[:30]:
            log(f"  {src} | {ns} | {bid} | {tb} : {cnt}")

        if total_kn > 0:
            log(f"Missing source_span rate (sample): {missing_span / total_kn * 100:.2f}%")
            log(f"Missing evidence in span rate (sample): {missing_evidence / total_kn * 100:.2f}%")
            log(f"Missing book_id rate (sample): {missing_book / total_kn * 100:.2f}%")

    except Exception as e:
        log(f"Error during knowledge_nodes query: {str(e)[:300]}")

    # === document_chunks audit ===
    log("\n--- document_chunks audit ---")
    try:
        res = client.table("document_chunks").select(
            "document_name, related_node_id"
        ).execute()

        total_dc = len(res.data)
        log(f"Sampled document_chunks rows: {total_dc}")

        dc_by_textbook = defaultdict(int)
        unlinked = 0
        for row in res.data:
            doc = row.get("document_name") or "NULL"
            dc_by_textbook[doc] += 1
            if not row.get("related_node_id"):
                unlinked += 1

        log("document_chunks per textbook (top):")
        for doc, cnt in sorted(dc_by_textbook.items(), key=lambda x: -x[1])[:20]:
            log(f"  {doc}: {cnt}")

        if total_dc > 0:
            log(f"Unlinked chunks rate (sample): {unlinked / total_dc * 100:.2f}%")

    except Exception as e:
        log(f"Error during document_chunks query: {str(e)[:300]}")

    # === Recommended raw SQL for full accurate GROUP BY (run in Supabase SQL Editor) ===
    log("\n--- Exact Read-Only SQL to run in Supabase SQL Editor (SERVICE_ROLE, read-only) ---")
    sql_statements = """
-- 1. Full knowledge_nodes source distribution + missing rates
SELECT 
    COALESCE(source, 'NULL') as source,
    COALESCE(node_source, 'NULL') as node_source,
    COALESCE(book_id, 'NULL') as book_id,
    COALESCE(textbook, 'NULL') as textbook,
    COUNT(*) as cnt,
    COUNT(*) FILTER (WHERE source_span IS NULL OR source_span = '{}'::jsonb) as missing_source_span,
    COUNT(*) FILTER (WHERE (source_span->>'evidence') IS NULL OR (source_span->>'evidence') = '') as missing_evidence,
    COUNT(*) FILTER (WHERE (source_span->>'parent_entity') IS NULL) as missing_parent_entity,
    COUNT(*) FILTER (WHERE book_id IS NULL) as missing_book_id
FROM knowledge_nodes
GROUP BY source, node_source, book_id, textbook
ORDER BY textbook, source, cnt DESC;

-- 2. Per-textbook pipeline source breakdown
SELECT 
    textbook,
    COUNT(*) FILTER (WHERE source = 'pipeline_v3') as v3_count,
    COUNT(*) FILTER (WHERE source IN ('textbook_pipeline', 'textbook_auto')) as old_pipelines_count,
    COUNT(*) FILTER (WHERE source = 'seed') as seed_count,
    COUNT(*) as total
FROM knowledge_nodes
GROUP BY textbook
HAVING COUNT(*) > 0
ORDER BY total DESC;

-- 3. document_chunks per textbook + linking stats
SELECT 
    document_name,
    COUNT(*) as chunk_count,
    COUNT(DISTINCT related_node_id) as linked_nodes,
    COUNT(*) FILTER (WHERE related_node_id IS NULL) as unlinked_chunks
FROM document_chunks
GROUP BY document_name
ORDER BY chunk_count DESC;

-- 4. Anomalous / unclassifiable sources
SELECT source, COUNT(*) as cnt 
FROM knowledge_nodes 
WHERE source NOT IN ('pipeline_v3', 'textbook_pipeline', 'textbook_auto', 'seed') 
   OR source IS NULL
GROUP BY source;
"""
    log(sql_statements)

    end_time = datetime.datetime.now().isoformat()
    log(f"\n=== Stage 3A Audit END: {end_time} ===")
    log("Please copy the SQL above into Supabase SQL Editor and run it.")
    log("Save the full output of this script and the SQL results together for auditability.")
    log("Do NOT run any UPDATE, DELETE, or migration commands.")

    # Additional recommended only-read queries per feedback (knowledge_nodes stats + RPC test + coverage)
    log("\n--- Additional only-read for full Stage 3A (run in SQL Editor or extend this script) ---")
    additional_sql = """
-- knowledge_nodes for canonical book_id = 'internal-medicine-10' (v3 naming) - separate denominator
SELECT 
    'internal-medicine-10 (book_id)' as filter,
    COALESCE(source, 'NULL') as source,
    COALESCE(node_source, 'NULL') as node_source,
    COUNT(*) as nodes,
    COUNT(*) FILTER (WHERE source_span IS NULL OR source_span = '{}'::jsonb) as missing_source_span,
    COUNT(*) FILTER (WHERE (source_span->>'evidence') IS NULL OR (source_span->>'evidence') = '') as missing_evidence,
    COUNT(*) FILTER (WHERE (source_span->>'parent_entity') IS NULL) as missing_parent_entity,
    COUNT(*) FILTER (WHERE content IS NULL OR content = '') as missing_content
FROM knowledge_nodes
WHERE book_id = 'internal-medicine-10'
GROUP BY source, node_source
ORDER BY source, nodes DESC;

-- knowledge_nodes for old textbook name = '内科学（第10版）' - separate denominator
SELECT 
    '内科学（第10版） (textbook)' as filter,
    COALESCE(source, 'NULL') as source,
    COALESCE(node_source, 'NULL') as node_source,
    COUNT(*) as nodes,
    COUNT(*) FILTER (WHERE source_span IS NULL OR source_span = '{}'::jsonb) as missing_source_span,
    COUNT(*) FILTER (WHERE (source_span->>'evidence') IS NULL OR (source_span->>'evidence') = '') as missing_evidence,
    COUNT(*) FILTER (WHERE (source_span->>'parent_entity') IS NULL) as missing_parent_entity,
    COUNT(*) FILTER (WHERE content IS NULL OR content = '') as missing_content
FROM knowledge_nodes
WHERE textbook = '内科学（第10版）'
GROUP BY source, node_source
ORDER BY source, nodes DESC;

-- Exact coverage CTE for the 24 nodes (v3 name, user-provided, with orphan detection)
WITH linked AS (
  SELECT DISTINCT related_node_id
  FROM document_chunks
  WHERE document_name = 'internal-medicine-10'
    AND related_node_id IS NOT NULL
),
textbook_nodes AS (
  SELECT id
  FROM knowledge_nodes
  WHERE book_id = 'internal-medicine-10'
)
SELECT
  (SELECT COUNT(*) FROM textbook_nodes) AS total_nodes,
  COUNT(*) FILTER (WHERE tn.id IS NOT NULL) AS covered_nodes,
  COUNT(*) FILTER (WHERE tn.id IS NULL) AS orphan_node_refs,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE tn.id IS NOT NULL)
    / NULLIF((SELECT COUNT(*) FROM textbook_nodes), 0),
    2
  ) AS coverage_pct
FROM linked l
LEFT JOIN textbook_nodes tn ON tn.id::text = l.related_node_id;

-- Parallel coverage CTE for old name (separate denominator)
WITH linked_old AS (
  SELECT DISTINCT related_node_id
  FROM document_chunks
  WHERE document_name = '内科学（第10版）'
    AND related_node_id IS NOT NULL
),
textbook_nodes_old AS (
  SELECT id
  FROM knowledge_nodes
  WHERE textbook = '内科学（第10版）'
)
SELECT
  '内科学（第10版） (textbook name)' as filter,
  (SELECT COUNT(*) FROM textbook_nodes_old) AS total_nodes,
  COUNT(*) FILTER (WHERE tn.id IS NOT NULL) AS covered_nodes,
  COUNT(*) FILTER (WHERE tn.id IS NULL) AS orphan_node_refs,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE tn.id IS NOT NULL)
    / NULLIF((SELECT COUNT(*) FROM textbook_nodes_old), 0),
    2
  ) AS coverage_pct
FROM linked_old l
LEFT JOIN textbook_nodes_old tn ON tn.id::text = l.related_node_id;
"""
    log(additional_sql)

if __name__ == "__main__":
    main()

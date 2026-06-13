-- ============================================================
-- Medlearn: Pipeline Infrastructure Migration
-- Run this in Supabase SQL Editor or via CLI:
--   supabase db push  (if using local dev)
-- ============================================================

-- 1. Pipeline 运行记录
-- 每次 pipeline 运行（parse/auto）生成一条记录
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  book_id          TEXT NOT NULL,            -- e.g. 'internal-medicine-10'
  source_file      TEXT NOT NULL,            -- 原始 PDF 文件名
  status           TEXT NOT NULL DEFAULT 'running',  -- running | success | failed
  pipeline_version TEXT NOT NULL,            -- e.g. '2.0.0'
  stages           JSONB NOT NULL DEFAULT '{}',
  -- stages JSONB 结构示例:
  -- {
  --   "reader":   {"status":"success","duration_ms":2300,"pages":387,"toc_entries":12},
  --   "segment":  {"status":"success","duration_ms":100,"matched":23,"total":23},
  --   "nodes":    {"status":"success","duration_ms":50,"nodes":48,"weak_defs":5},
  --   "validate": {"status":"success","duration_ms":30,"errors":0,"warnings":2}
  -- }
  started_at       TIMESTAMPTZ DEFAULT NOW(),
  finished_at      TIMESTAMPTZ,
  error_message    TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_book   ON pipeline_runs(book_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);


-- 2. Pipeline 输出快照
-- 每次成功运行生成一份完整快照，用于历史回溯和 App 端展示
CREATE TABLE IF NOT EXISTS pipeline_snapshots (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  run_id          UUID REFERENCES pipeline_runs(id) ON DELETE SET NULL,
  book_id         TEXT NOT NULL,
  total_nodes     INT NOT NULL DEFAULT 0,
  total_segments  INT NOT NULL DEFAULT 0,
  nodes_data      JSONB NOT NULL DEFAULT '{}',   -- nodes.staging.json 内容
  segments_data   JSONB,                         -- segments.jsonl 汇总
  validation      JSONB,                         -- validation-report.json 内容
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_snapshots_book ON pipeline_snapshots(book_id);


-- 3. (可选) 扩展 knowledge_nodes 表
-- 如果 knowledge_nodes 表还没有以下字段，取消注释执行：
--
-- ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS node_source TEXT;
-- ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS inferred BOOLEAN DEFAULT FALSE;
-- ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS heading_score REAL;
-- ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS content_hash TEXT;
-- ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS page_start INT;
-- ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS page_end INT;
-- ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS textbook TEXT;


-- 4. RLS 策略（Supabase 默认启用 RLS）
-- pipeline_runs 和 pipeline_snapshots 通常只有 service role 可写，
-- 匿名用户只读（用于 App 端历史查看）。

ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_snapshots ENABLE ROW LEVEL SECURITY;

-- 允许匿名读取（App 端查看历史）
CREATE POLICY "Allow anonymous read pipeline_runs"
  ON pipeline_runs FOR SELECT USING (true);

CREATE POLICY "Allow anonymous read pipeline_snapshots"
  ON pipeline_snapshots FOR SELECT USING (true);

-- 禁止匿名写入（只允许 service role）
-- Supabase anon key 默认不能写入，但如果启用了其他策略需要显式拒绝：
-- CREATE POLICY "Deny anonymous insert pipeline_runs"
--   ON pipeline_runs FOR INSERT WITH CHECK (false);

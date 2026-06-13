-- Textbook pipeline run history and chunk-to-node lookup support.

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  book_id TEXT NOT NULL,
  source_file TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
  pipeline_version TEXT NOT NULL,
  stages JSONB NOT NULL DEFAULT '{}',
  started_at TIMESTAMPTZ DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_book
  ON public.pipeline_runs(book_id);

CREATE TABLE IF NOT EXISTS public.pipeline_snapshots (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  run_id UUID REFERENCES public.pipeline_runs(id) ON DELETE SET NULL,
  book_id TEXT NOT NULL,
  total_nodes INT NOT NULL DEFAULT 0,
  total_segments INT NOT NULL DEFAULT 0,
  nodes_data JSONB NOT NULL DEFAULT '{}',
  segments_data JSONB,
  validation JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_snapshots_book
  ON public.pipeline_snapshots(book_id);

DO $$
BEGIN
  IF to_regclass('public.document_chunks') IS NULL THEN
    RAISE EXCEPTION 'public.document_chunks does not exist; run migration 002 first';
  END IF;

  ALTER TABLE public.document_chunks
    ADD COLUMN IF NOT EXISTS related_node_id TEXT;

  EXECUTE
    'CREATE INDEX IF NOT EXISTS idx_document_chunks_related_node '
    'ON public.document_chunks (related_node_id)';
END
$$;

ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow anonymous read pipeline_runs" ON public.pipeline_runs;
DROP POLICY IF EXISTS "Allow anonymous read pipeline_snapshots" ON public.pipeline_snapshots;
DROP POLICY IF EXISTS "Authenticated users can read pipeline runs" ON public.pipeline_runs;
CREATE POLICY "Authenticated users can read pipeline runs"
  ON public.pipeline_runs FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read pipeline snapshots" ON public.pipeline_snapshots;
CREATE POLICY "Authenticated users can read pipeline snapshots"
  ON public.pipeline_snapshots FOR SELECT TO authenticated USING (true);

GRANT SELECT ON public.pipeline_runs TO authenticated;
GRANT SELECT ON public.pipeline_snapshots TO authenticated;
GRANT ALL ON public.pipeline_runs TO service_role;
GRANT ALL ON public.pipeline_snapshots TO service_role;

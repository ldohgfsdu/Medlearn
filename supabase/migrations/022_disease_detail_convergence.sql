-- Stable textbook catalog and disease identities for route convergence.

CREATE TABLE IF NOT EXISTS public.chapter_sections (
  chapter_section_id TEXT PRIMARY KEY,
  textbook_series_id TEXT NOT NULL,
  source_textbook_version_ids TEXT[] NOT NULL DEFAULT '{}',
  catalog_path TEXT NOT NULL,
  display_title TEXT NOT NULL,
  parent_section_id TEXT REFERENCES public.chapter_sections(chapter_section_id),
  order_index INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (textbook_series_id, catalog_path)
);

CREATE INDEX IF NOT EXISTS idx_chapter_sections_parent_order
  ON public.chapter_sections(parent_section_id, order_index);

CREATE INDEX IF NOT EXISTS idx_chapter_sections_catalog
  ON public.chapter_sections(textbook_series_id, catalog_path);

CREATE TABLE IF NOT EXISTS public.disease_entities (
  disease_id TEXT PRIMARY KEY,
  canonical_disease_name TEXT NOT NULL,
  canonical_key TEXT NOT NULL,
  aliases TEXT[] NOT NULL DEFAULT '{}',
  source_textbook_series_id TEXT NOT NULL,
  source_chapter_section_ids TEXT[] NOT NULL DEFAULT '{}',
  confidence NUMERIC(4, 3) NOT NULL DEFAULT 0
    CHECK (confidence >= 0 AND confidence <= 1),
  resolution_status TEXT NOT NULL DEFAULT 'review_required'
    CHECK (resolution_status IN ('confirmed', 'review_required', 'rejected')),
  resolution_reason TEXT,
  resolved_at TIMESTAMPTZ,
  resolved_by TEXT
    CHECK (resolved_by IS NULL OR resolved_by IN ('pipeline', 'script', 'manual')),
  resolution_version INTEGER NOT NULL DEFAULT 1,
  normalization_version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (
    resolution_status <> 'rejected'
    OR (
      resolution_reason IS NOT NULL
      AND resolved_at IS NOT NULL
      AND resolved_by IS NOT NULL
      AND resolution_version > 0
    )
  ),
  UNIQUE (source_textbook_series_id, canonical_key)
);

CREATE INDEX IF NOT EXISTS idx_disease_entities_canonical_key
  ON public.disease_entities(canonical_key);

CREATE INDEX IF NOT EXISTS idx_disease_entities_resolution
  ON public.disease_entities(resolution_status);

ALTER TABLE public.knowledge_nodes
  ADD COLUMN IF NOT EXISTS disease_id TEXT,
  ADD COLUMN IF NOT EXISTS chapter_section_id TEXT,
  ADD COLUMN IF NOT EXISTS aspect TEXT,
  ADD COLUMN IF NOT EXISTS raw_aspect TEXT,
  ADD COLUMN IF NOT EXISTS display_title TEXT,
  ADD COLUMN IF NOT EXISTS content_class TEXT;

ALTER TABLE public.knowledge_nodes
  DROP CONSTRAINT IF EXISTS knowledge_nodes_disease_id_fkey,
  ADD CONSTRAINT knowledge_nodes_disease_id_fkey
    FOREIGN KEY (disease_id)
    REFERENCES public.disease_entities(disease_id);

ALTER TABLE public.knowledge_nodes
  DROP CONSTRAINT IF EXISTS knowledge_nodes_chapter_section_id_fkey,
  ADD CONSTRAINT knowledge_nodes_chapter_section_id_fkey
    FOREIGN KEY (chapter_section_id)
    REFERENCES public.chapter_sections(chapter_section_id);

ALTER TABLE public.knowledge_nodes
  DROP CONSTRAINT IF EXISTS knowledge_nodes_aspect_check,
  ADD CONSTRAINT knowledge_nodes_aspect_check CHECK (
    aspect IS NULL OR aspect IN (
      'definition',
      'epidemiology',
      'etiology',
      'pathogenesis',
      'clinical_manifestation',
      'diagnosis',
      'differential_diagnosis',
      'treatment',
      'prognosis',
      'prevention',
      'other'
    )
  );

ALTER TABLE public.knowledge_nodes
  DROP CONSTRAINT IF EXISTS knowledge_nodes_content_class_check,
  ADD CONSTRAINT knowledge_nodes_content_class_check CHECK (
    content_class IS NULL OR content_class IN (
      'confirmed_disease',
      'non_disease_knowledge',
      'suspected_disease',
      'invalid'
    )
  );

ALTER TABLE public.knowledge_nodes
  DROP CONSTRAINT IF EXISTS knowledge_nodes_identity_consistency_check,
  ADD CONSTRAINT knowledge_nodes_identity_consistency_check CHECK (
    content_class IS NULL
    OR (
      content_class = 'confirmed_disease'
      AND disease_id IS NOT NULL
      AND chapter_section_id IS NOT NULL
    )
    OR (
      content_class = 'non_disease_knowledge'
      AND disease_id IS NULL
      AND chapter_section_id IS NOT NULL
    )
    OR (
      content_class = 'suspected_disease'
      AND disease_id IS NULL
    )
    OR (
      content_class = 'invalid'
      AND disease_id IS NULL
    )
  );

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_disease_id
  ON public.knowledge_nodes(disease_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_disease_aspect
  ON public.knowledge_nodes(disease_id, aspect);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_chapter_order
  ON public.knowledge_nodes(chapter_section_id, order_num);

ALTER TABLE public.causal_chains
  ADD COLUMN IF NOT EXISTS disease_id TEXT
    REFERENCES public.disease_entities(disease_id),
  ADD COLUMN IF NOT EXISTS content_hash TEXT,
  ADD COLUMN IF NOT EXISTS generator_version INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS validation_status TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS validation_errors JSONB NOT NULL DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS evidence_coverage NUMERIC(4, 3) NOT NULL DEFAULT 0
    CHECK (evidence_coverage >= 0 AND evidence_coverage <= 1);

ALTER TABLE public.causal_chains
  DROP CONSTRAINT IF EXISTS causal_chains_validation_status_check,
  ADD CONSTRAINT causal_chains_validation_status_check CHECK (
    validation_status IN (
      'pending',
      'valid',
      'invalid_structure',
      'invalid_evidence',
      'invalid_medical_logic',
      'review_required'
    )
  );

CREATE INDEX IF NOT EXISTS idx_causal_chains_disease_status
  ON public.causal_chains(disease_id, validation_status);

ALTER TABLE public.chapter_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.disease_entities ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS chapter_sections_select ON public.chapter_sections;
CREATE POLICY chapter_sections_select
  ON public.chapter_sections FOR SELECT
  USING (true);

DROP POLICY IF EXISTS disease_entities_select ON public.disease_entities;
CREATE POLICY disease_entities_select
  ON public.disease_entities FOR SELECT
  USING (resolution_status = 'confirmed');

GRANT SELECT ON public.chapter_sections TO anon, authenticated;
GRANT SELECT ON public.disease_entities TO anon, authenticated;

DROP TRIGGER IF EXISTS update_chapter_sections_updated_at ON public.chapter_sections;
CREATE TRIGGER update_chapter_sections_updated_at
  BEFORE UPDATE ON public.chapter_sections
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_disease_entities_updated_at ON public.disease_entities;
CREATE TRIGGER update_disease_entities_updated_at
  BEFORE UPDATE ON public.disease_entities
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

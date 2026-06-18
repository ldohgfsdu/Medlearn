ALTER TABLE public.chapter_sections
  ADD COLUMN IF NOT EXISTS node_type TEXT NOT NULL DEFAULT 'category',
  ADD COLUMN IF NOT EXISTS content_status TEXT NOT NULL DEFAULT 'in_progress';

ALTER TABLE public.chapter_sections
  DROP CONSTRAINT IF EXISTS chapter_sections_node_type_check,
  ADD CONSTRAINT chapter_sections_node_type_check CHECK (
    node_type IN ('textbook', 'system', 'category', 'overview')
  ),
  DROP CONSTRAINT IF EXISTS chapter_sections_content_status_check,
  ADD CONSTRAINT chapter_sections_content_status_check CHECK (
    content_status IN ('available', 'in_progress', 'unavailable')
  );

ALTER TABLE public.disease_entities
  ADD COLUMN IF NOT EXISTS node_type TEXT NOT NULL DEFAULT 'disease',
  ADD COLUMN IF NOT EXISTS content_status TEXT NOT NULL DEFAULT 'in_progress';

ALTER TABLE public.disease_entities
  DROP CONSTRAINT IF EXISTS disease_entities_node_type_check,
  ADD CONSTRAINT disease_entities_node_type_check CHECK (node_type = 'disease'),
  DROP CONSTRAINT IF EXISTS disease_entities_content_status_check,
  ADD CONSTRAINT disease_entities_content_status_check CHECK (
    content_status IN ('available', 'in_progress', 'unavailable')
  );

CREATE INDEX IF NOT EXISTS idx_disease_entities_content_status
  ON public.disease_entities(content_status, resolution_status);

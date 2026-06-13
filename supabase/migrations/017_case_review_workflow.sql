ALTER TABLE public.case_templates
    ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_notes TEXT;

ALTER TABLE public.case_templates
    DROP CONSTRAINT IF EXISTS case_templates_approval_requires_reviewer;

UPDATE public.case_templates
SET review_status = 'reviewed'
WHERE review_status = 'approved'
  AND (reviewed_by IS NULL OR reviewed_at IS NULL);

ALTER TABLE public.case_templates
    ADD CONSTRAINT case_templates_approval_requires_reviewer
    CHECK (
        review_status <> 'approved'
        OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    )
    NOT VALID;

ALTER TABLE public.case_templates
    VALIDATE CONSTRAINT case_templates_approval_requires_reviewer;

COMMENT ON COLUMN public.case_templates.reviewed_by IS
    'Qualified medical reviewer who approved the case.';
COMMENT ON COLUMN public.case_templates.reviewed_at IS
    'Timestamp of the latest medical approval.';
COMMENT ON COLUMN public.case_templates.review_notes IS
    'Internal reviewer notes; never exposed to authenticated clients.';

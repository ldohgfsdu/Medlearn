-- Harden case usage counting so authenticated users can count only their own
-- session, and each session contributes at most once.

ALTER TABLE case_sessions
  ADD COLUMN IF NOT EXISTS usage_counted_at TIMESTAMPTZ;

DROP FUNCTION IF EXISTS increment_usage_count(TEXT);

CREATE OR REPLACE FUNCTION increment_usage_count(p_session_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_case_id TEXT;
BEGIN
  UPDATE case_sessions
  SET usage_counted_at = NOW()
  WHERE id = p_session_id
    AND user_id = auth.uid()
    AND usage_counted_at IS NULL
  RETURNING case_id INTO v_case_id;

  IF v_case_id IS NULL THEN
    RETURN FALSE;
  END IF;

  UPDATE case_templates
  SET usage_count = usage_count + 1
  WHERE id = v_case_id;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION increment_usage_count(UUID) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION increment_usage_count(UUID) TO authenticated, service_role;

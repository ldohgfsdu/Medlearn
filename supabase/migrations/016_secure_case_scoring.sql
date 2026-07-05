-- Keep answer keys and scoring rules server-side.
REVOKE SELECT ON TABLE public.case_templates FROM authenticated;

GRANT SELECT (
    id,
    case_code,
    title,
    chief_complaint,
    specialty,
    difficulty,
    estimated_minutes,
    demographics,
    is_active,
    review_status,
    usage_count,
    average_score,
    completion_rate,
    created_at,
    updated_at
) ON TABLE public.case_templates TO authenticated;

DROP POLICY IF EXISTS "case_templates_select" ON public.case_templates;
CREATE POLICY "case_templates_select_approved"
ON public.case_templates
FOR SELECT
TO authenticated
USING (is_active = true AND review_status = 'approved');

-- Users may save progress, but final scores can only be written by service-role code.
DROP POLICY IF EXISTS "case_sessions_update" ON public.case_sessions;
CREATE POLICY "case_sessions_update_progress"
ON public.case_sessions
FOR UPDATE
TO authenticated
USING (auth.uid() = user_id AND status = 'in_progress')
WITH CHECK (
    auth.uid() = user_id
    AND status = 'in_progress'
    AND score IS NULL
    AND completed_at IS NULL
);

CREATE OR REPLACE FUNCTION public.protect_case_session_server_fields()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF auth.role() = 'authenticated' AND (
        NEW.user_id IS DISTINCT FROM OLD.user_id
        OR NEW.case_id IS DISTINCT FROM OLD.case_id
        OR NEW.status IS DISTINCT FROM OLD.status
        OR NEW.score IS DISTINCT FROM OLD.score
        OR NEW.completed_at IS DISTINCT FROM OLD.completed_at
        OR NEW.duration_seconds IS DISTINCT FROM OLD.duration_seconds
        OR NEW.xp_earned IS DISTINCT FROM OLD.xp_earned
        OR NEW.total_tokens IS DISTINCT FROM OLD.total_tokens
        OR NEW.total_cost IS DISTINCT FROM OLD.total_cost
        OR NEW.usage_counted_at IS DISTINCT FROM OLD.usage_counted_at
        OR NEW.max_hints IS DISTINCT FROM OLD.max_hints
        OR NEW.hints_used < OLD.hints_used
        OR NEW.hints_used > OLD.hints_used + 1
        OR NEW.hints_used > NEW.max_hints
    ) THEN
        RAISE EXCEPTION 'case session server-managed fields cannot be changed';
    END IF;
    RETURN NEW;
END;
$$;

ALTER TABLE public.case_sessions
    DROP CONSTRAINT IF EXISTS case_sessions_valid_hint_count;
ALTER TABLE public.case_sessions
    ADD CONSTRAINT case_sessions_valid_hint_count
    CHECK (hints_used >= 0 AND max_hints >= 0 AND hints_used <= max_hints);

DROP TRIGGER IF EXISTS protect_case_session_server_fields ON public.case_sessions;
CREATE TRIGGER protect_case_session_server_fields
BEFORE UPDATE ON public.case_sessions
FOR EACH ROW
EXECUTE FUNCTION public.protect_case_session_server_fields();

CREATE OR REPLACE FUNCTION public.record_case_llm_usage(
    p_session_id UUID,
    p_prompt_tokens INTEGER,
    p_completion_tokens INTEGER,
    p_total_tokens INTEGER,
    p_estimated_cost NUMERIC
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF auth.role() <> 'service_role' THEN
        RAISE EXCEPTION 'service role required';
    END IF;

    UPDATE public.case_sessions
    SET
        total_tokens = COALESCE(total_tokens, 0) + GREATEST(COALESCE(p_total_tokens, 0), 0),
        total_cost = COALESCE(total_cost, 0) + GREATEST(COALESCE(p_estimated_cost, 0), 0)
    WHERE id = p_session_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'case session not found';
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.record_case_llm_usage(UUID, INTEGER, INTEGER, INTEGER, NUMERIC)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_case_llm_usage(UUID, INTEGER, INTEGER, INTEGER, NUMERIC)
TO service_role;

CREATE INDEX IF NOT EXISTS idx_case_events_safety
ON public.case_events(event_name, created_at DESC)
WHERE event_name IN (
    'prompt_injection_detected',
    'diagnosis_leakage_detected',
    'llm_error'
);

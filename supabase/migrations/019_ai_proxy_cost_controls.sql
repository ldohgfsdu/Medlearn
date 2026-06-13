-- Per-user AI proxy usage tracking and quota enforcement.

CREATE TABLE IF NOT EXISTS public.ai_proxy_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    prompt_tokens INTEGER NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
    completion_tokens INTEGER NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
    total_tokens INTEGER NOT NULL DEFAULT 0 CHECK (total_tokens >= 0),
    estimated_cost NUMERIC(12, 6) NOT NULL DEFAULT 0 CHECK (estimated_cost >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_proxy_usage_user_created
    ON public.ai_proxy_usage(user_id, created_at DESC);

ALTER TABLE public.ai_proxy_usage ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_proxy_usage_select_own"
    ON public.ai_proxy_usage
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.check_ai_proxy_quota(
    p_user_id UUID,
    p_window_minutes INTEGER DEFAULT 60,
    p_max_requests INTEGER DEFAULT 60,
    p_max_tokens INTEGER DEFAULT 100000
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    request_count INTEGER;
    token_sum INTEGER;
BEGIN
    IF auth.role() <> 'service_role' THEN
        RAISE EXCEPTION 'service role required';
    END IF;

    SELECT
        COUNT(*)::INTEGER,
        COALESCE(SUM(total_tokens), 0)::INTEGER
    INTO request_count, token_sum
    FROM public.ai_proxy_usage
    WHERE user_id = p_user_id
      AND created_at >= NOW() - make_interval(mins => GREATEST(p_window_minutes, 1));

    RETURN request_count < GREATEST(p_max_requests, 1)
       AND token_sum < GREATEST(p_max_tokens, 1);
END;
$$;

CREATE OR REPLACE FUNCTION public.record_ai_proxy_usage(
    p_user_id UUID,
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

    INSERT INTO public.ai_proxy_usage (
        user_id,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        estimated_cost
    )
    VALUES (
        p_user_id,
        GREATEST(COALESCE(p_prompt_tokens, 0), 0),
        GREATEST(COALESCE(p_completion_tokens, 0), 0),
        GREATEST(COALESCE(p_total_tokens, 0), 0),
        GREATEST(COALESCE(p_estimated_cost, 0), 0)
    );
END;
$$;

REVOKE ALL ON FUNCTION public.check_ai_proxy_quota(UUID, INTEGER, INTEGER, INTEGER)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.check_ai_proxy_quota(UUID, INTEGER, INTEGER, INTEGER)
TO service_role;

REVOKE ALL ON FUNCTION public.record_ai_proxy_usage(UUID, INTEGER, INTEGER, INTEGER, NUMERIC)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_ai_proxy_usage(UUID, INTEGER, INTEGER, INTEGER, NUMERIC)
TO service_role;
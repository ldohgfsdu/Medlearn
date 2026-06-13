-- Allow increment_usage_count() to mark usage_counted_at once per session.
-- Migration 016 blocked all usage_counted_at updates for authenticated callers.

CREATE OR REPLACE FUNCTION public.protect_case_session_server_fields()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF auth.role() = 'authenticated' THEN
        IF NEW.usage_counted_at IS DISTINCT FROM OLD.usage_counted_at
           AND OLD.usage_counted_at IS NULL
           AND NEW.usage_counted_at IS NOT NULL
           AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id
           AND NEW.case_id IS NOT DISTINCT FROM OLD.case_id
           AND NEW.status IS NOT DISTINCT FROM OLD.status
           AND NEW.score IS NOT DISTINCT FROM OLD.score
           AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at
           AND NEW.duration_seconds IS NOT DISTINCT FROM OLD.duration_seconds
           AND NEW.xp_earned IS NOT DISTINCT FROM OLD.xp_earned
           AND NEW.total_tokens IS NOT DISTINCT FROM OLD.total_tokens
           AND NEW.total_cost IS NOT DISTINCT FROM OLD.total_cost
           AND NEW.max_hints IS NOT DISTINCT FROM OLD.max_hints
           AND NEW.hints_used IS NOT DISTINCT FROM OLD.hints_used
        THEN
            RETURN NEW;
        END IF;

        IF (
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
    END IF;
    RETURN NEW;
END;
$$;
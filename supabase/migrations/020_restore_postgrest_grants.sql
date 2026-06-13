-- Restore PostgREST role grants when migrations are applied outside `supabase db push`.
-- Without these, service_role and authenticated clients get "permission denied".

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.case_templates TO service_role;

GRANT SELECT (
    id,
    case_code,
    title,
    chief_complaint,
    specialty,
    difficulty,
    estimated_minutes,
    demographics,
    patient_world,
    is_active,
    review_status,
    usage_count,
    average_score,
    completion_rate,
    created_at,
    updated_at
) ON TABLE public.case_templates TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.case_sessions TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.case_sessions TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.case_messages TO service_role;
GRANT SELECT, INSERT ON TABLE public.case_messages TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.case_events TO service_role;
GRANT SELECT, INSERT ON TABLE public.case_events TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.ai_proxy_usage TO service_role;
GRANT SELECT, INSERT ON TABLE public.ai_proxy_usage TO authenticated;
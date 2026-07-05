-- Keep the hidden patient world behind service-role Edge Functions.
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

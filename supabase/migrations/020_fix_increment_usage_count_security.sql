-- Fix: Add search_path to increment_usage_count for security hardening
CREATE OR REPLACE FUNCTION increment_usage_count(case_id TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE case_templates
    SET usage_count = usage_count + 1
    WHERE id = case_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp;

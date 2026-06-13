-- Fix security issues: admin privilege escalation, anonymous access to sensitive views
-- Created: 2026-06-09

-- ============================================================
-- a) Fix admin privilege escalation (affects 004 and 005)
-- ============================================================

-- Create user_roles table for proper role management
CREATE TABLE IF NOT EXISTS user_roles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

-- Only service_role can modify
CREATE POLICY "service_role_only" ON user_roles FOR ALL USING (auth.role() = 'service_role');

-- Users can read their own role
CREATE POLICY "users_read_own" ON user_roles FOR SELECT USING (auth.uid() = user_id);

-- Create helper function to check admin status
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM user_roles WHERE user_id = auth.uid() AND role = 'admin'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE SET search_path = public, pg_temp;

-- Drop and recreate admin policies on medical_issue_reports (from 004)
DROP POLICY IF EXISTS "medical_issue_reports_admin_select" ON medical_issue_reports;
CREATE POLICY "medical_issue_reports_admin_select" ON medical_issue_reports
    FOR SELECT USING (is_admin());

DROP POLICY IF EXISTS "medical_issue_reports_admin_update" ON medical_issue_reports;
CREATE POLICY "medical_issue_reports_admin_update" ON medical_issue_reports
    FOR UPDATE USING (is_admin());

-- Drop and recreate admin policies on case_events (from 005)
DROP POLICY IF EXISTS "case_events_admin_select" ON case_events;
CREATE POLICY "case_events_admin_select" ON case_events
    FOR SELECT USING (is_admin());

-- ============================================================
-- b) Revoke anonymous access to sensitive views
-- ============================================================

REVOKE SELECT ON user_learning_stats FROM anon;
REVOKE SELECT ON node_mastery FROM anon;

-- ============================================================
-- c) Grant necessary permissions to authenticated users
-- ============================================================

GRANT SELECT ON user_learning_stats TO authenticated;
GRANT SELECT ON node_mastery TO authenticated;

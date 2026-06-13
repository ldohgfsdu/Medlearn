-- MVP event tracking for case funnel and safety events
-- Created: 2026-06-06

CREATE TABLE IF NOT EXISTS case_events (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    event_name TEXT NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    session_id UUID REFERENCES case_sessions(id) ON DELETE SET NULL,
    case_id TEXT REFERENCES case_templates(id) ON DELETE SET NULL,
    chief_complaint TEXT,
    difficulty TEXT,
    properties JSONB DEFAULT '{}',
    app_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_case_events_name ON case_events(event_name);
CREATE INDEX IF NOT EXISTS idx_case_events_user ON case_events(user_id);
CREATE INDEX IF NOT EXISTS idx_case_events_session ON case_events(session_id);
CREATE INDEX IF NOT EXISTS idx_case_events_case ON case_events(case_id);
CREATE INDEX IF NOT EXISTS idx_case_events_created ON case_events(created_at DESC);

ALTER TABLE case_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "case_events_insert_own" ON case_events
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "case_events_select_own" ON case_events
    FOR SELECT USING (auth.uid() = user_id);

-- Admin: 可读取所有事件（用于分析仪表盘）
CREATE POLICY "case_events_admin_select" ON case_events
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND (preferences->>'role') = 'admin')
    );


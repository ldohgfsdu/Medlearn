-- Medical issue reports for MVP safety review
-- Created: 2026-06-06

CREATE TABLE IF NOT EXISTS medical_issue_reports (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES case_sessions(id) ON DELETE SET NULL,
    case_id TEXT REFERENCES case_templates(id) ON DELETE SET NULL,

    issue_type TEXT NOT NULL DEFAULT 'medical_content' CHECK (issue_type IN (
        'medical_content',
        'scoring',
        'diagnosis_leakage',
        'unsafe_advice',
        'other'
    )),
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'reviewing', 'resolved', 'dismissed')),
    reviewer_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_medical_issue_reports_user ON medical_issue_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_medical_issue_reports_case ON medical_issue_reports(case_id);
CREATE INDEX IF NOT EXISTS idx_medical_issue_reports_status ON medical_issue_reports(status);
CREATE INDEX IF NOT EXISTS idx_medical_issue_reports_created ON medical_issue_reports(created_at DESC);

ALTER TABLE medical_issue_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "medical_issue_reports_select_own" ON medical_issue_reports
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "medical_issue_reports_insert_own" ON medical_issue_reports
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "medical_issue_reports_update_own_open" ON medical_issue_reports
    FOR UPDATE USING (auth.uid() = user_id AND status = 'open')
    WITH CHECK (auth.uid() = user_id AND status = 'open');

CREATE TRIGGER update_medical_issue_reports_updated_at
    BEFORE UPDATE ON medical_issue_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Admin/Reviewer: 可读取所有报告，可更新状态和 reviewer_notes
CREATE POLICY "medical_issue_reports_admin_select" ON medical_issue_reports
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND (preferences->>'role') = 'admin')
    );

CREATE POLICY "medical_issue_reports_admin_update" ON medical_issue_reports
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM user_profiles WHERE id = auth.uid() AND (preferences->>'role') = 'admin')
    );


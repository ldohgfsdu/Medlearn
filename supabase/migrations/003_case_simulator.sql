-- Case Simulator 扩展 Schema
-- 基于 PRD 第 39 章和第 65 章
-- 创建日期: 2026-06-06

-- ============================================
-- 0. 触发器函数（C1 fix: 确保函数存在）
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ============================================
-- 1. 病例模板表
-- ============================================

CREATE TABLE IF NOT EXISTS case_templates (
    id TEXT PRIMARY KEY,
    case_code VARCHAR(20) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    chief_complaint TEXT NOT NULL,
    specialty TEXT,
    difficulty TEXT NOT NULL CHECK (difficulty IN ('beginner', 'intermediate', 'advanced')),
    estimated_minutes INTEGER DEFAULT 15,

    -- 三层数据（JSONB）
    demographics JSONB NOT NULL,
    patient_world JSONB NOT NULL,
    ground_truth JSONB NOT NULL,
    scoring_rubric JSONB NOT NULL,

    -- 状态
    is_active BOOLEAN DEFAULT true,
    review_status TEXT DEFAULT 'draft' CHECK (review_status IN ('draft', 'reviewed', 'approved')),

    -- 统计
    usage_count INTEGER DEFAULT 0,
    average_score DECIMAL(5,2),
    completion_rate DECIMAL(5,2),

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 2. 病例会话表
-- ============================================

CREATE TABLE IF NOT EXISTS case_sessions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL REFERENCES case_templates(id),

    -- 状态
    status TEXT DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned', 'timeout')),
    current_phase TEXT DEFAULT 'intro' CHECK (current_phase IN (
        'intro', 'history', 'exam', 'tests', 'diagnosis', 'treatment', 'scoring', 'feedback'
    )),

    -- 状态数据（JSONB）
    revealed JSONB DEFAULT '{"historyFields":[],"examPerformed":[],"testsOrdered":[],"testsResultsReleased":[]}',
    submitted JSONB DEFAULT '{}',

    -- 帮助
    hints_used INTEGER DEFAULT 0,
    max_hints INTEGER DEFAULT 3,

    -- 时间
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    turn_count INTEGER DEFAULT 0,

    -- 评分
    score JSONB,
    xp_earned INTEGER DEFAULT 0,

    -- AI 使用
    total_tokens INTEGER DEFAULT 0,
    total_cost DECIMAL(10,6) DEFAULT 0,

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 3. 病例消息表
-- ============================================

CREATE TABLE IF NOT EXISTS case_messages (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES case_sessions(id) ON DELETE CASCADE,

    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'text',

    -- 元数据
    turn_number INTEGER NOT NULL,
    intent_type TEXT,
    intent_target TEXT,
    intent_confidence DECIMAL(3,2),

    -- AI 使用
    model_used TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    latency_ms INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 4. 索引
-- ============================================

CREATE INDEX idx_case_templates_complaint ON case_templates(chief_complaint);
CREATE INDEX idx_case_templates_difficulty ON case_templates(difficulty);
CREATE INDEX idx_case_templates_active ON case_templates(is_active);

CREATE INDEX idx_case_sessions_user ON case_sessions(user_id);
CREATE INDEX idx_case_sessions_case ON case_sessions(case_id);
CREATE INDEX idx_case_sessions_status ON case_sessions(status);
CREATE INDEX idx_case_sessions_user_status ON case_sessions(user_id, status);

CREATE INDEX idx_case_messages_session ON case_messages(session_id);
CREATE INDEX idx_case_messages_turn ON case_messages(session_id, turn_number);

-- ============================================
-- 5. RLS
-- ============================================

ALTER TABLE case_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_messages ENABLE ROW LEVEL SECURITY;

-- 病例模板：已认证用户可读，service role 可写
CREATE POLICY "case_templates_select" ON case_templates
    FOR SELECT USING (auth.role() = 'authenticated');

-- 病例会话
CREATE POLICY "case_sessions_select" ON case_sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "case_sessions_insert" ON case_sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "case_sessions_update" ON case_sessions
    FOR UPDATE USING (auth.uid() = user_id);

-- C7 fix: 允许用户删除自己的会话
CREATE POLICY "case_sessions_delete" ON case_sessions
    FOR DELETE USING (auth.uid() = user_id);

-- 病例消息
CREATE POLICY "case_messages_select" ON case_messages
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM case_sessions
            WHERE case_sessions.id = case_messages.session_id
            AND case_sessions.user_id = auth.uid()
        )
    );

CREATE POLICY "case_messages_insert" ON case_messages
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM case_sessions
            WHERE case_sessions.id = case_messages.session_id
            AND case_sessions.user_id = auth.uid()
        )
    );

-- ============================================
-- 6. RPC 函数
-- ============================================

-- C2 fix: 原子递增 usage_count
CREATE OR REPLACE FUNCTION increment_usage_count(case_id TEXT)
RETURNS VOID AS $$
BEGIN
    UPDATE case_templates
    SET usage_count = usage_count + 1
    WHERE id = case_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- M11 fix: 计算 duration_seconds
CREATE OR REPLACE FUNCTION calculate_duration_seconds()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND OLD.completed_at IS NULL THEN
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at))::INTEGER;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 7. 触发器
-- ============================================

CREATE TRIGGER update_case_templates_updated_at
    BEFORE UPDATE ON case_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_case_sessions_updated_at
    BEFORE UPDATE ON case_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- M11 fix: 完成时自动计算时长
CREATE TRIGGER calculate_case_duration
    BEFORE UPDATE ON case_sessions
    FOR EACH ROW EXECUTE FUNCTION calculate_duration_seconds();

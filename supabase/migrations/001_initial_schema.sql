-- Medlearn 数据库 Schema
-- 适用于 Supabase (PostgreSQL)
-- 创建日期: 2026-06-03

-- ============================================
-- 1. 启用必要的扩展
-- ============================================

-- 启用 UUID 生成
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 2. 静态数据表（种子数据）
-- ============================================

-- 知识点表
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id TEXT PRIMARY KEY,
    order_num INTEGER DEFAULT 0,
    level INTEGER,
    type TEXT NOT NULL CHECK (type IN ('concept', 'mechanism', 'disease', 'symptom', 'treatment', 'exam')),
    title TEXT NOT NULL,
    subject TEXT,
    chapter TEXT,
    sub_chapter TEXT,
    knowledge_path TEXT[],
    content TEXT,
    key_points TEXT[],
    causal_links JSONB DEFAULT '[]',
    related_nodes TEXT[],
    difficulty INTEGER DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
    tags TEXT[],
    source TEXT DEFAULT 'seed',
    book_id TEXT,
    textbook TEXT,
    edition TEXT,
    node_source TEXT,
    inferred BOOLEAN DEFAULT FALSE,
    source_span JSONB,
    version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 考试题目表
CREATE TABLE IF NOT EXISTS exam_questions (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('single', 'multiple')),
    question TEXT NOT NULL,
    options TEXT[] NOT NULL,
    answer INTEGER NOT NULL,
    explanation TEXT,
    related_nodes TEXT[],
    difficulty INTEGER DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
    source TEXT DEFAULT 'seed',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 推导链表
CREATE TABLE IF NOT EXISTS causal_chains (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    steps JSONB NOT NULL DEFAULT '[]',
    related_nodes TEXT[],
    difficulty INTEGER DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
    source TEXT DEFAULT 'seed',
    creator_user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 病例表
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    chief_complaint TEXT NOT NULL,
    stages JSONB NOT NULL DEFAULT '[]',
    difficulty INTEGER DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
    related_nodes TEXT[],
    source TEXT DEFAULT 'seed',
    creator_user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 3. 用户数据表
-- ============================================

-- 用户资料表
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nickname TEXT,
    avatar_url TEXT,
    preferences JSONB DEFAULT '{}',
    ai_config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 费曼复述记录表
CREATE TABLE IF NOT EXISTS feynman_records (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    transcript TEXT NOT NULL,
    ai_score JSONB NOT NULL DEFAULT '{}',
    feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 对话记录表
CREATE TABLE IF NOT EXISTS dialogue_records (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    messages JSONB NOT NULL DEFAULT '[]',
    mastery_detected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 病例练习记录表
CREATE TABLE IF NOT EXISTS case_records (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL REFERENCES cases(id),
    current_stage INTEGER DEFAULT 0,
    stage_scores JSONB DEFAULT '{}',
    total_score INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 答题记录表
CREATE TABLE IF NOT EXISTS exam_records (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id UUID NOT NULL,
    question_id TEXT NOT NULL REFERENCES exam_questions(id),
    user_answer INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 考试会话表
CREATE TABLE IF NOT EXISTS exam_sessions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_ids TEXT[] NOT NULL,
    score INTEGER DEFAULT 0,
    weak_nodes TEXT[],
    duration INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 错题表
CREATE TABLE IF NOT EXISTS wrong_questions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES exam_questions(id),
    node_id TEXT REFERENCES knowledge_nodes(id),
    session_id UUID,
    retry_correct BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 间隔重复计划表
CREATE TABLE IF NOT EXISTS spaced_repetition (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    next_review TIMESTAMPTZ NOT NULL,
    interval INTEGER DEFAULT 1,
    ease_factor REAL DEFAULT 2.5,
    repetitions INTEGER DEFAULT 0,
    last_quality INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, node_id)
);

-- 学习活动表
CREATE TABLE IF NOT EXISTS study_activities (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('feynman', 'exam', 'pathway', 'case', 'dialogue', 'compare')),
    node_id TEXT REFERENCES knowledge_nodes(id),
    session_id UUID,
    record_id UUID,
    score INTEGER,
    duration INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 收藏表
CREATE TABLE IF NOT EXISTS favorites (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, node_id)
);

-- 学习路径表
CREATE TABLE IF NOT EXISTS learning_paths (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    node_ids TEXT[] NOT NULL DEFAULT '{}',
    progress INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 学习计划表
CREATE TABLE IF NOT EXISTS study_plans (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    goals JSONB DEFAULT '[]',
    schedule JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 学习目标表
CREATE TABLE IF NOT EXISTS study_goals (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    target INTEGER NOT NULL,
    current INTEGER DEFAULT 0,
    period TEXT NOT NULL CHECK (period IN ('daily', 'weekly', 'monthly')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 4. 创建索引
-- ============================================

-- 知识点索引
CREATE INDEX idx_knowledge_nodes_subject ON knowledge_nodes(subject);
CREATE INDEX idx_knowledge_nodes_chapter ON knowledge_nodes(chapter);
CREATE INDEX idx_knowledge_nodes_type ON knowledge_nodes(type);

-- 用户数据索引
CREATE INDEX idx_feynman_records_user ON feynman_records(user_id);
CREATE INDEX idx_feynman_records_node ON feynman_records(node_id);
CREATE INDEX idx_dialogue_records_user ON dialogue_records(user_id);
CREATE INDEX idx_case_records_user ON case_records(user_id);
CREATE INDEX idx_exam_records_user ON exam_records(user_id);
CREATE INDEX idx_exam_sessions_user ON exam_sessions(user_id);
CREATE INDEX idx_wrong_questions_user ON wrong_questions(user_id);
CREATE INDEX idx_spaced_repetition_user ON spaced_repetition(user_id);
CREATE INDEX idx_spaced_repetition_next_review ON spaced_repetition(user_id, next_review);
CREATE INDEX idx_study_activities_user ON study_activities(user_id);
CREATE INDEX idx_study_activities_type ON study_activities(user_id, type);
CREATE INDEX idx_favorites_user ON favorites(user_id);

-- ============================================
-- 5. 启用 Row Level Security (RLS)
-- ============================================

-- 静态数据表：所有已认证用户可读，只有管理员可写
ALTER TABLE knowledge_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE causal_chains ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;

-- 用户数据表：用户只能访问自己的数据
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE feynman_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE dialogue_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE wrong_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaced_repetition ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_goals ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 6. 创建 RLS 策略
-- ============================================

-- 静态数据表：已认证用户可读
CREATE POLICY "knowledge_nodes_select" ON knowledge_nodes
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "exam_questions_select" ON exam_questions
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "causal_chains_select" ON causal_chains
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "cases_select" ON cases
    FOR SELECT USING (auth.role() = 'authenticated');

-- 用户资料表：用户只能访问和修改自己的资料
CREATE POLICY "user_profiles_select" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "user_profiles_insert" ON user_profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "user_profiles_update" ON user_profiles
    FOR UPDATE USING (auth.uid() = id);

-- 费曼复述记录：用户只能访问自己的记录
CREATE POLICY "feynman_records_select" ON feynman_records
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "feynman_records_insert" ON feynman_records
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "feynman_records_delete" ON feynman_records
    FOR DELETE USING (auth.uid() = user_id);

-- 对话记录：用户只能访问自己的记录
CREATE POLICY "dialogue_records_select" ON dialogue_records
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "dialogue_records_insert" ON dialogue_records
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "dialogue_records_delete" ON dialogue_records
    FOR DELETE USING (auth.uid() = user_id);

-- 病例练习记录：用户只能访问自己的记录
CREATE POLICY "case_records_select" ON case_records
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "case_records_insert" ON case_records
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "case_records_update" ON case_records
    FOR UPDATE USING (auth.uid() = user_id);

-- 答题记录：用户只能访问自己的记录
CREATE POLICY "exam_records_select" ON exam_records
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "exam_records_insert" ON exam_records
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 考试会话：用户只能访问自己的记录
CREATE POLICY "exam_sessions_select" ON exam_sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "exam_sessions_insert" ON exam_sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "exam_sessions_update" ON exam_sessions
    FOR UPDATE USING (auth.uid() = user_id);

-- 错题：用户只能访问自己的记录
CREATE POLICY "wrong_questions_select" ON wrong_questions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "wrong_questions_insert" ON wrong_questions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "wrong_questions_update" ON wrong_questions
    FOR UPDATE USING (auth.uid() = user_id);

-- 间隔重复计划：用户只能访问自己的记录
CREATE POLICY "spaced_repetition_select" ON spaced_repetition
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "spaced_repetition_insert" ON spaced_repetition
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "spaced_repetition_update" ON spaced_repetition
    FOR UPDATE USING (auth.uid() = user_id);

-- 学习活动：用户只能访问自己的记录
CREATE POLICY "study_activities_select" ON study_activities
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "study_activities_insert" ON study_activities
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 收藏：用户只能访问自己的记录
CREATE POLICY "favorites_select" ON favorites
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "favorites_insert" ON favorites
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "favorites_delete" ON favorites
    FOR DELETE USING (auth.uid() = user_id);

-- 学习路径：用户只能访问自己的记录
CREATE POLICY "learning_paths_select" ON learning_paths
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "learning_paths_insert" ON learning_paths
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "learning_paths_update" ON learning_paths
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "learning_paths_delete" ON learning_paths
    FOR DELETE USING (auth.uid() = user_id);

-- 学习计划：用户只能访问自己的记录
CREATE POLICY "study_plans_select" ON study_plans
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "study_plans_insert" ON study_plans
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "study_plans_update" ON study_plans
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "study_plans_delete" ON study_plans
    FOR DELETE USING (auth.uid() = user_id);

-- 学习目标：用户只能访问自己的记录
CREATE POLICY "study_goals_select" ON study_goals
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "study_goals_insert" ON study_goals
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "study_goals_update" ON study_goals
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "study_goals_delete" ON study_goals
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================
-- 7. 创建触发器函数
-- ============================================

-- 自动更新 updated_at 字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要的表创建触发器
CREATE TRIGGER update_knowledge_nodes_updated_at
    BEFORE UPDATE ON knowledge_nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_exam_questions_updated_at
    BEFORE UPDATE ON exam_questions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_causal_chains_updated_at
    BEFORE UPDATE ON causal_chains
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cases_updated_at
    BEFORE UPDATE ON cases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_case_records_updated_at
    BEFORE UPDATE ON case_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_exam_sessions_updated_at
    BEFORE UPDATE ON exam_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_wrong_questions_updated_at
    BEFORE UPDATE ON wrong_questions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_spaced_repetition_updated_at
    BEFORE UPDATE ON spaced_repetition
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_learning_paths_updated_at
    BEFORE UPDATE ON learning_paths
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_study_plans_updated_at
    BEFORE UPDATE ON study_plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_study_goals_updated_at
    BEFORE UPDATE ON study_goals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 8. 创建用户注册触发器
-- ============================================

-- 用户注册时自动创建用户资料
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, nickname, avatar_url)
    VALUES (NEW.id, NEW.raw_user_meta_data->>'nickname', NEW.raw_user_meta_data->>'avatar_url');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================
-- 9. 创建统计视图
-- ============================================

-- 用户学习统计视图
CREATE OR REPLACE VIEW user_learning_stats AS
SELECT
    user_id,
    COUNT(DISTINCT CASE WHEN type = 'feynman' THEN id END) AS feynman_count,
    COUNT(DISTINCT CASE WHEN type = 'exam' THEN id END) AS exam_count,
    COUNT(DISTINCT CASE WHEN type = 'pathway' THEN id END) AS pathway_count,
    COUNT(DISTINCT CASE WHEN type = 'case' THEN id END) AS case_count,
    SUM(duration) AS total_duration,
    COUNT(DISTINCT DATE(created_at)) AS study_days
FROM study_activities
GROUP BY user_id;

-- 知识点掌握度视图
CREATE OR REPLACE VIEW node_mastery AS
SELECT
    fr.user_id,
    fr.node_id,
    kn.title AS node_title,
    kn.subject,
    AVG((fr.ai_score->>'accuracy')::int) AS avg_accuracy,
    AVG((fr.ai_score->>'completeness')::int) AS avg_completeness,
    AVG((fr.ai_score->>'clarity')::int) AS avg_clarity,
    AVG((fr.ai_score->>'depth')::int) AS avg_depth,
    COUNT(*) AS attempt_count,
    MAX(fr.created_at) AS last_attempt
FROM feynman_records fr
JOIN knowledge_nodes kn ON fr.node_id = kn.id
GROUP BY fr.user_id, fr.node_id, kn.title, kn.subject;

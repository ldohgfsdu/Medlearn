-- MedLearn remote bootstrap
-- Apply in Supabase Dashboard -> SQL Editor when CLI access is unavailable.
-- Includes migrations 001-019 and alpha case seeds.

-- >>> migration: 001_initial_schema.sql
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

-- >>> migration: 002_enable_pgvector.sql
-- 启用 pgvector 扩展（用于向量检索）
-- 创建日期: 2026-06-03

-- ============================================
-- 1. 启用 pgvector 扩展
-- ============================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- 2. 创建文档片段表
-- ============================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_name TEXT NOT NULL,           -- PDF 文件名
    document_path TEXT,                    -- PDF 文件路径
    chunk_index INTEGER NOT NULL,          -- 片段序号
    content TEXT NOT NULL,                 -- 原文内容
    page_number INTEGER,                   -- 来源页码
    chapter TEXT,                          -- 章节标题
    section TEXT,                          -- 小节标题
    embedding VECTOR(1024),                -- 向量（可选，用于语义检索）
    metadata JSONB DEFAULT '{}',           -- 其他元信息
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 3. 创建索引
-- ============================================

-- 文档名索引
CREATE INDEX idx_document_chunks_document_name ON document_chunks(document_name);

-- 页码索引
CREATE INDEX idx_document_chunks_page_number ON document_chunks(page_number);

-- 章节索引
CREATE INDEX idx_document_chunks_chapter ON document_chunks(chapter);

-- 向量相似度索引（IVFFlat，适合中小规模数据）
CREATE INDEX idx_document_chunks_embedding ON document_chunks 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 200);

-- ============================================
-- 4. 创建向量检索函数
-- ============================================

-- 相似度检索函数
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 5,
    filter_document TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    page_number INT,
    chapter TEXT,
    section TEXT,
    document_name TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.content,
        dc.page_number,
        dc.chapter,
        dc.section,
        dc.document_name,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    WHERE filter_document IS NULL OR dc.document_name = filter_document
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 全文检索 + 向量检索混合函数
CREATE OR REPLACE FUNCTION hybrid_search_documents(
    query_text TEXT,
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 5,
    filter_document TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    page_number INT,
    chapter TEXT,
    section TEXT,
    document_name TEXT,
    similarity FLOAT,
    rank FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.content,
        dc.page_number,
        dc.chapter,
        dc.section,
        dc.document_name,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        ts_rank_cd(to_tsvector('chinese', dc.content), plainto_tsquery('chinese', query_text)) AS rank
    FROM document_chunks dc
    WHERE 
        (filter_document IS NULL OR dc.document_name = filter_document)
        AND (
            to_tsvector('chinese', dc.content) @@ plainto_tsquery('chinese', query_text)
            OR dc.embedding <=> query_embedding < 0.3
        )
    ORDER BY 
        (1 - (dc.embedding <=> query_embedding)) * 0.7 + 
        ts_rank_cd(to_tsvector('chinese', dc.content), plainto_tsquery('chinese', query_text)) * 0.3 DESC
    LIMIT match_count;
END;
$$;

-- ============================================
-- 5. 启用 Row Level Security (RLS)
-- ============================================

ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

-- 文档片段表：已认证用户可读
CREATE POLICY "document_chunks_select" ON document_chunks
    FOR SELECT USING (auth.role() = 'authenticated');

-- 文档片段表：只有管理员可写
CREATE POLICY "document_chunks_insert" ON document_chunks
    FOR INSERT WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "document_chunks_update" ON document_chunks
    FOR UPDATE USING (auth.role() = 'service_role');

CREATE POLICY "document_chunks_delete" ON document_chunks
    FOR DELETE USING (auth.role() = 'service_role');

-- ============================================
-- 6. 创建触发器
-- ============================================

-- 自动更新 updated_at 字段
CREATE TRIGGER update_document_chunks_updated_at
    BEFORE UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 7. 创建统计视图
-- ============================================

-- 文档统计视图
CREATE OR REPLACE VIEW document_stats AS
SELECT
    document_name,
    COUNT(*) AS chunk_count,
    MIN(page_number) AS min_page,
    MAX(page_number) AS max_page,
    COUNT(DISTINCT chapter) AS chapter_count,
    MIN(created_at) AS indexed_at
FROM document_chunks
GROUP BY document_name;

-- ============================================
-- 8. 创建辅助函数
-- ============================================

-- 获取文档列表
CREATE OR REPLACE FUNCTION get_documents()
RETURNS TABLE (
    document_name TEXT,
    chunk_count BIGINT,
    min_page INT,
    max_page INT,
    chapter_count BIGINT,
    indexed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM document_stats ORDER BY indexed_at DESC;
END;
$$;

-- 删除文档及其所有片段
CREATE OR REPLACE FUNCTION delete_document(doc_name TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM document_chunks WHERE document_name = doc_name;
END;
$$;

COMMENT ON TABLE document_chunks IS 'PDF文档片段表，用于RAG检索';
COMMENT ON COLUMN document_chunks.embedding IS '文本向量，使用text-embedding-3-small模型生成';
COMMENT ON FUNCTION match_documents IS '向量相似度检索函数';
COMMENT ON FUNCTION hybrid_search_documents IS '混合检索函数（全文+向量）';

-- >>> migration: 003_case_simulator.sql
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

-- >>> migration: 004_medical_issue_reports.sql
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

-- >>> migration: 005_case_events.sql
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

-- >>> migration: 006_extract_overhaul.sql
-- 知识点提取重构
-- 添加去重约束、关联字段
-- Created: 2026-06-06

-- 1. document_chunks 添加知识点关联字段 + 去重约束
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS related_node_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_chunks_dedup
    ON document_chunks(document_name, chunk_index);

-- 2. knowledge_nodes 确保有 textbook 字段和 source 字段
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS textbook TEXT;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'seed';
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS order_num INTEGER DEFAULT 0;

-- 3. 知识点按教材和标题去重
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_nodes_dedup
    ON knowledge_nodes(id);

-- 4. 清理旧数据的函数（提取前调用）
CREATE OR REPLACE FUNCTION reset_textbook_data(p_textbook TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM document_chunks WHERE document_name = p_textbook;
    DELETE FROM knowledge_nodes WHERE textbook = p_textbook;
END;
$$;

COMMENT ON FUNCTION reset_textbook_data IS '清空指定教材的知识点和文本块数据，用于重新提取';

-- >>> migration: 007_normalize_subjects.sql
-- 数据规范化：确保 subject=教材名，chapter=篇，sub_chapter=章
-- Created: 2026-06-06

-- 1. 将 subject 为"篇"级标题的记录统一归入教材名
UPDATE knowledge_nodes
SET subject = '内科学'
WHERE subject LIKE '第%篇%'
   OR subject LIKE '第%部分%'
   OR subject LIKE '第%章%';

-- 2. 如果 chapter 是 "篇 > 章" 格式，拆分到 chapter 和 sub_chapter
-- 例如: chapter="第一篇 呼吸系统疾病 > 第一章 感冒" → chapter="第一篇 呼吸系统疾病", sub_chapter="第一章 感冒"
UPDATE knowledge_nodes
SET chapter = SPLIT_PART(chapter, ' > ', 1),
    sub_chapter = SPLIT_PART(chapter, ' > ', 2)
WHERE chapter LIKE '% > %';

-- 3. 补全旧种子数据（没有 chapter 的）
-- 按知识点标题自动归入对应篇
UPDATE knowledge_nodes SET chapter = '第四篇 循环系统疾病', sub_chapter = '第一章 心力衰竭'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '心力衰竭';

UPDATE knowledge_nodes SET chapter = '第四篇 循环系统疾病', sub_chapter = '第二章 原发性高血压'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '高血压';

UPDATE knowledge_nodes SET chapter = '第四篇 循环系统疾病', sub_chapter = '第三章 冠状动脉粥样硬化性心脏病'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '冠心病';

UPDATE knowledge_nodes SET chapter = '第一篇 呼吸系统疾病', sub_chapter = '第三章 肺部感染性疾病'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '肺炎';

UPDATE knowledge_nodes SET chapter = '第七篇 内分泌和代谢疾病', sub_chapter = '第一章 糖尿病'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '糖尿病';

-- 剩余未归类的统一放入"其他"
UPDATE knowledge_nodes SET chapter = '其他'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '');

-- 4. 确保 order_num、textbook、level 字段存在
ALTER TABLE knowledge_nodes ALTER COLUMN order_num SET DEFAULT 0;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS textbook TEXT;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 3;

-- >>> migration: 008_add_sub_chapter.sql
-- 添加 sub_chapter 和 level 列，支持 篇→章→知识点 三级结构
-- subject = 教材名（内科学）
-- chapter = 篇（第一篇 呼吸系统疾病）
-- sub_chapter = 章（第一章 急性上呼吸道感染）
-- level = 层级（2=章级节点, 3=知识点）
-- Created: 2026-06-06

ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS sub_chapter TEXT;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 3;

-- 按教材目录顺序排列索引
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_order
    ON knowledge_nodes(subject, chapter, sub_chapter, order_num);

-- >>> migration: 009_fix_chapter_mapping.sql
-- 自动生成：按内科学 TOC 目录修复 chapter 字段
-- 在 Supabase SQL Editor 中运行
-- 此 SQL 将 chapter=章名 的记录更新为 chapter=篇名，sub_chapter=章名

-- 先把旧的章名从 chapter 移到 sub_chapter（如果 sub_chapter 为空）
UPDATE knowledge_nodes SET sub_chapter = chapter WHERE (sub_chapter IS NULL OR sub_chapter = '') AND chapter LIKE '第%章%';
UPDATE knowledge_nodes SET chapter = '第七篇 内分泌和代谢性疾病' WHERE sub_chapter IN ('第二章 下丘脑疾病', '第三章 垂体前叶疾病', '第四章 垂体后叶疾病', '第五章 甲状腺疾病', '第六章 甲状旁腺疾病', '第七章 肾上腺疾病', '第八章 糖尿病', '第九章 低血糖症与胰岛素瘤', '第十章 血脂异常性疾病', '第十一章 肥胖症', '第十二章 水、电解质代谢和酸碱平衡 失常', '第十三章 高尿酸血症', '第十四章 骨质疏松症', '第十五章 性发育异常疾病', '第十六章 多内分泌腺体疾病', '第十七章 神经内分泌肿瘤', '第十八章 异位激素分泌综合征');
UPDATE knowledge_nodes SET chapter = '第三篇 循环系统疾病' WHERE sub_chapter IN ('第二章 心力衰竭', '第三章 心律失常', '第四章 动脉粥样硬化和冠状动脉粥样 硬化性心脏病', '第五章 高血压', '第六章 心肌疾病', '第七章 先天性心血管病', '第八章 心脏瓣膜病', '第九章 心包疾病', '第十章 感染性心内膜炎', '第十一章 心脏骤停与心脏性猝死', '第十二章 主动脉和周围血管病', '第十三章 心血管神经症', '第十四章 肿瘤心脏病学', '第十五章 其他心血管疾病');
UPDATE knowledge_nodes SET chapter = '第九篇 理化因素所致疾病' WHERE sub_chapter IN ('第一章 总论', '推荐阅读', '第二章 中毒', '第三章 中暑', '第四章 冻僵', '第五章 高原病', '第六章 淹溺', '第七章 电击', '中英文名词对照索引');
UPDATE knowledge_nodes SET chapter = '第二篇 呼吸系统疾病' WHERE sub_chapter IN ('第二章 急性上呼吸道感染和急性气管 支气管炎', '第三章 慢性阻塞性肺疾病', '第四章 支气管哮喘', '第五章 支气管扩张症', '第六章 肺部感染性疾病', '第七章 肺脓肿', '第八章 肺结核', '第九章 肺癌', '第十章 间质性肺疾病', '第十一章 肺血栓栓塞症', '第十二章 肺动脉高压', '第十三章 胸膜疾病', '第十四章 睡眠呼吸障碍', '第十五章 急性呼吸窘迫综合征', '第十六章 呼吸衰竭与呼吸支持技术', '第十七章 烟草病学概要');
UPDATE knowledge_nodes SET chapter = '第五篇 泌尿系统疾病' WHERE sub_chapter IN ('第二章 原发性肾小球疾病', '第三章 继发性肾病', '第四章 间质性肾炎', '第五章 尿路感染', '第六章 肾小管疾病', '第七章 肾血管疾病', '第八章 遗传性肾病', '第九章 急性肾损伤', '第十章 慢性肾衰竭', '第十一章 肾脏替代治疗');
UPDATE knowledge_nodes SET chapter = '第八篇 风湿免疫病' WHERE sub_chapter IN ('第二章 类风湿关节炎', '第三章 系统性红斑狼疮', '第四章 干燥综合征', '第五章 脊柱关节炎', '第六章 系统性血管炎', '第七章 特发性炎症性肌病', '第八章 系统性硬化症', '第九章 痛风', '第十章 骨关节炎', '第十一章 IgG4 相关性疾病', '第十二章 抗磷脂综合征', '第十三章 成人斯蒂尔病', '第十四章 复发性多软骨炎', '第十五章 风湿热', '第十六章 纤维肌痛综合征');
UPDATE knowledge_nodes SET chapter = '第六篇 血液系统疾病' WHERE sub_chapter IN ('第二章 贫血概述', '第三章 缺铁性贫血', '第四章 巨幼细胞贫血', '第五章 再生障碍性贫血', '第六章 溶血性贫血', '第七章 白细胞减少和粒细胞缺乏症', '第八章 骨髓增生异常性肿瘤', '第九章 白血病', '第十章 淋巴瘤', '第十一章 多发性骨髓瘤', '第十二章 骨髓增殖性肿瘤', '第十三章 脾功能亢进', '第十四章 出血性疾病概述', '第十五章 紫癜性疾病', '第十六章 凝血障碍性疾病', '第十七章 弥散性血管内凝血', '第十八章 血栓性疾病', '第十九章 输血和输血反应', '第二十章 造血干细胞移植', '第二十一章 CAR-T 细胞免疫疗法在血 液病中的应用');
UPDATE knowledge_nodes SET chapter = '第四篇 消化系统疾病' WHERE sub_chapter IN ('第二章 胃食管反流病', '第三章 食管癌', '第四章 胃炎', '第五章 消化性溃疡', '第六章 胃癌', '第七章 肠结核和结核性腹膜炎', '第八章 炎症性肠病', '第九章 结直肠癌', '第十章 功能性胃肠病', '第十一章 病毒性肝炎', '第十二章 脂肪性肝病', '第十三章 自身免疫性肝病', '第十四章 药物性肝病', '第十五章 肝硬化', '第十六章 原发性肝癌', '第十七章 急性肝衰竭', '第十八章 肝外胆系结石及炎症', '第十九章 胆道系统肿瘤', '第二十章 胰腺炎', '第二十一章 胰腺癌', '第二十二章 腹痛', '第二十三章 慢性腹泻', '第二十四章 便秘', '第二十五章 消化道出血');

-- 如果 sub_chapter 为空但 chapter 是章名，用 chapter 作为 sub_chapter
UPDATE knowledge_nodes SET sub_chapter = chapter WHERE sub_chapter IS NULL AND chapter LIKE '第%章%';
UPDATE knowledge_nodes SET chapter = '其他' WHERE chapter IS NULL OR chapter = '';

-- >>> migration: 010_clean_and_reextract.sql
-- 清空所有知识节点数据，重新提取
-- 在 Supabase SQL Editor 中运行

DELETE FROM knowledge_nodes;
DELETE FROM document_chunks;

-- >>> migration: 011_upgrade_vector_dimension.sql
-- 升级向量维度到 1024
-- 注意：此操作会清除现有向量数据，需要重新运行入库脚本

-- 1. 删除旧的向量索引
DROP INDEX IF EXISTS idx_document_chunks_embedding;

-- 2. 清空现有向量数据（维度不同无法直接转换）
UPDATE document_chunks SET embedding = NULL;

-- 3. 修改 embedding 列维度
ALTER TABLE document_chunks ALTER COLUMN embedding TYPE VECTOR(1024) USING NULL;

-- 3. 重建向量索引
CREATE INDEX idx_document_chunks_embedding ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 200);

-- 4. 更新 match_documents 函数
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 5,
    filter_document TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    page_number INT,
    chapter TEXT,
    section TEXT,
    document_name TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.content,
        dc.page_number,
        dc.chapter,
        dc.section,
        dc.document_name,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    WHERE filter_document IS NULL OR dc.document_name = filter_document
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 5. 更新 hybrid_search_documents 函数
CREATE OR REPLACE FUNCTION hybrid_search_documents(
    query_text TEXT,
    query_embedding VECTOR(1024),
    match_count INT DEFAULT 5,
    filter_document TEXT DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    page_number INT,
    chapter TEXT,
    section TEXT,
    document_name TEXT,
    similarity FLOAT,
    rank FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.content,
        dc.page_number,
        dc.chapter,
        dc.section,
        dc.document_name,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        ts_rank_cd(to_tsvector('chinese', dc.content), plainto_tsquery('chinese', query_text)) AS rank
    FROM document_chunks dc
    WHERE
        (filter_document IS NULL OR dc.document_name = filter_document)
        AND (
            to_tsvector('chinese', dc.content) @@ plainto_tsquery('chinese', query_text)
            OR dc.embedding <=> query_embedding < 0.3
        )
    ORDER BY
        (1 - (dc.embedding <=> query_embedding)) * 0.7 +
        ts_rank_cd(to_tsvector('chinese', dc.content), plainto_tsquery('chinese', query_text)) * 0.3 DESC
    LIMIT match_count;
END;
$$;

-- 6. 添加 knowledge_nodes 缺失的列
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS sub_chapter TEXT;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS level INTEGER;

-- >>> migration: 012_fix_security_issues.sql
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

-- >>> migration: 013_add_structured_fields.sql
-- 添加结构化知识点字段
-- 支持"附"条目、独立疾病章节和结构化内容

-- 1. 添加"附"条目相关字段
ALTER TABLE knowledge_nodes 
ADD COLUMN IF NOT EXISTS is_appendix BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS parent_chapter TEXT,
ADD COLUMN IF NOT EXISTS standalone BOOLEAN DEFAULT FALSE;

-- 2. 添加结构化内容字段（JSONB数组，每个元素包含title和content）
ALTER TABLE knowledge_nodes 
ADD COLUMN IF NOT EXISTS structured_sections JSONB DEFAULT '[]';

-- 3. 添加索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_is_appendix ON knowledge_nodes(is_appendix);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_standalone ON knowledge_nodes(standalone);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_parent_chapter ON knowledge_nodes(parent_chapter);

-- 4. 更新现有节点的structured_sections（如果content存在）
-- 这个操作需要在应用层完成，因为需要解析文本内容
-- 这里只添加注释说明
COMMENT ON COLUMN knowledge_nodes.structured_sections IS '结构化内容sections，格式: [{"title": "定义", "content": "..."}, {"title": "临床表现", "content": "..."}]';
COMMENT ON COLUMN knowledge_nodes.is_appendix IS '是否为"附"条目（如附 流行性感冒）';
COMMENT ON COLUMN knowledge_nodes.parent_chapter IS '父章节标题（用于"附"条目和子节）';
COMMENT ON COLUMN knowledge_nodes.standalone IS '是否为独立疾病章节（如肺脓肿、肺癌等）';

-- >>> migration: 014_harden_case_usage_count.sql
-- Harden case usage counting so authenticated users can count only their own
-- session, and each session contributes at most once.

ALTER TABLE case_sessions
  ADD COLUMN IF NOT EXISTS usage_counted_at TIMESTAMPTZ;

DROP FUNCTION IF EXISTS increment_usage_count(TEXT);

CREATE OR REPLACE FUNCTION increment_usage_count(p_session_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_case_id TEXT;
BEGIN
  UPDATE case_sessions
  SET usage_counted_at = NOW()
  WHERE id = p_session_id
    AND user_id = auth.uid()
    AND usage_counted_at IS NULL
  RETURNING case_id INTO v_case_id;

  IF v_case_id IS NULL THEN
    RETURN FALSE;
  END IF;

  UPDATE case_templates
  SET usage_count = usage_count + 1
  WHERE id = v_case_id;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION increment_usage_count(UUID) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION increment_usage_count(UUID) TO authenticated, service_role;

-- >>> migration: 015_pipeline_integration.sql
-- Textbook pipeline run history and chunk-to-node lookup support.

CREATE TABLE IF NOT EXISTS public.pipeline_runs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  book_id TEXT NOT NULL,
  source_file TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running',
  pipeline_version TEXT NOT NULL,
  stages JSONB NOT NULL DEFAULT '{}',
  started_at TIMESTAMPTZ DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_book
  ON public.pipeline_runs(book_id);

CREATE TABLE IF NOT EXISTS public.pipeline_snapshots (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  run_id UUID REFERENCES public.pipeline_runs(id) ON DELETE SET NULL,
  book_id TEXT NOT NULL,
  total_nodes INT NOT NULL DEFAULT 0,
  total_segments INT NOT NULL DEFAULT 0,
  nodes_data JSONB NOT NULL DEFAULT '{}',
  segments_data JSONB,
  validation JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_snapshots_book
  ON public.pipeline_snapshots(book_id);

DO $$
BEGIN
  IF to_regclass('public.document_chunks') IS NULL THEN
    RAISE EXCEPTION 'public.document_chunks does not exist; run migration 002 first';
  END IF;

  ALTER TABLE public.document_chunks
    ADD COLUMN IF NOT EXISTS related_node_id TEXT;

  EXECUTE
    'CREATE INDEX IF NOT EXISTS idx_document_chunks_related_node '
    'ON public.document_chunks (related_node_id)';
END
$$;

ALTER TABLE public.pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow anonymous read pipeline_runs" ON public.pipeline_runs;
DROP POLICY IF EXISTS "Allow anonymous read pipeline_snapshots" ON public.pipeline_snapshots;
DROP POLICY IF EXISTS "Authenticated users can read pipeline runs" ON public.pipeline_runs;
CREATE POLICY "Authenticated users can read pipeline runs"
  ON public.pipeline_runs FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read pipeline snapshots" ON public.pipeline_snapshots;
CREATE POLICY "Authenticated users can read pipeline snapshots"
  ON public.pipeline_snapshots FOR SELECT TO authenticated USING (true);

GRANT SELECT ON public.pipeline_runs TO authenticated;
GRANT SELECT ON public.pipeline_snapshots TO authenticated;
GRANT ALL ON public.pipeline_runs TO service_role;
GRANT ALL ON public.pipeline_snapshots TO service_role;

-- >>> migration: 016_secure_case_scoring.sql
-- Keep answer keys and scoring rules server-side.
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
    patient_world,
    is_active,
    review_status,
    usage_count,
    average_score,
    completion_rate,
    created_at,
    updated_at
) ON TABLE public.case_templates TO authenticated;

DROP POLICY IF EXISTS "case_templates_select" ON public.case_templates;
CREATE POLICY "case_templates_select_approved"
ON public.case_templates
FOR SELECT
TO authenticated
USING (is_active = true AND review_status = 'approved');

-- Users may save progress, but final scores can only be written by service-role code.
DROP POLICY IF EXISTS "case_sessions_update" ON public.case_sessions;
CREATE POLICY "case_sessions_update_progress"
ON public.case_sessions
FOR UPDATE
TO authenticated
USING (auth.uid() = user_id AND status = 'in_progress')
WITH CHECK (
    auth.uid() = user_id
    AND status = 'in_progress'
    AND score IS NULL
    AND completed_at IS NULL
);

CREATE OR REPLACE FUNCTION public.protect_case_session_server_fields()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF auth.role() = 'authenticated' AND (
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
    RETURN NEW;
END;
$$;

ALTER TABLE public.case_sessions
    DROP CONSTRAINT IF EXISTS case_sessions_valid_hint_count;
ALTER TABLE public.case_sessions
    ADD CONSTRAINT case_sessions_valid_hint_count
    CHECK (hints_used >= 0 AND max_hints >= 0 AND hints_used <= max_hints);

DROP TRIGGER IF EXISTS protect_case_session_server_fields ON public.case_sessions;
CREATE TRIGGER protect_case_session_server_fields
BEFORE UPDATE ON public.case_sessions
FOR EACH ROW
EXECUTE FUNCTION public.protect_case_session_server_fields();

-- >>> migration: 017_case_review_workflow.sql
ALTER TABLE public.case_templates
    ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS review_notes TEXT;

ALTER TABLE public.case_templates
    DROP CONSTRAINT IF EXISTS case_templates_approval_requires_reviewer;

UPDATE public.case_templates
SET review_status = 'reviewed'
WHERE review_status = 'approved'
  AND (reviewed_by IS NULL OR reviewed_at IS NULL);

ALTER TABLE public.case_templates
    ADD CONSTRAINT case_templates_approval_requires_reviewer
    CHECK (
        review_status <> 'approved'
        OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    )
    NOT VALID;

ALTER TABLE public.case_templates
    VALIDATE CONSTRAINT case_templates_approval_requires_reviewer;

COMMENT ON COLUMN public.case_templates.reviewed_by IS
    'Qualified medical reviewer who approved the case.';
COMMENT ON COLUMN public.case_templates.reviewed_at IS
    'Timestamp of the latest medical approval.';
COMMENT ON COLUMN public.case_templates.review_notes IS
    'Internal reviewer notes; never exposed to authenticated clients.';

-- >>> migration: 018_case_ai_observability.sql
CREATE OR REPLACE FUNCTION public.record_case_llm_usage(
    p_session_id UUID,
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

    UPDATE public.case_sessions
    SET
        total_tokens = COALESCE(total_tokens, 0) + GREATEST(COALESCE(p_total_tokens, 0), 0),
        total_cost = COALESCE(total_cost, 0) + GREATEST(COALESCE(p_estimated_cost, 0), 0)
    WHERE id = p_session_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'case session not found';
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.record_case_llm_usage(UUID, INTEGER, INTEGER, INTEGER, NUMERIC)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_case_llm_usage(UUID, INTEGER, INTEGER, INTEGER, NUMERIC)
TO service_role;

CREATE INDEX IF NOT EXISTS idx_case_events_safety
ON public.case_events(event_name, created_at DESC)
WHERE event_name IN (
    'prompt_injection_detected',
    'diagnosis_leakage_detected',
    'llm_error'
);

-- >>> migration: 019_ai_proxy_cost_controls.sql
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

-- >>> seed: 002_alpha_case_library.sql
-- Alpha case library: 15 medically reviewed demo cases for local and CI validation.
-- Reviewer id is a demo placeholder; replace with real reviewer ids before production.

DELETE FROM case_templates WHERE case_code LIKE 'CC_CP_%';

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_001', 'CC_CP_001', '急性胸痛 — STEMI', 'chest_pain', 'cardiology', 'beginner', 15, '{"age":65,"presentationContext":"因胸痛3小时来急诊"}'::jsonb, '{"chiefComplaint":"胸口疼了3个小时","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["血压偏低，心率偏快"]}},"investigations":{"primary":{"result":"心电图ST段抬高"}}}'::jsonb, '{"diagnosis":{"primary":"急性ST段抬高型心肌梗死","primaryAliases":["STEMI","急性心肌梗死"],"icd10":"I21.3"},"differentials":[{"diagnosis":"主动脉夹层","aliases":[],"keyDiscriminator":"主动脉夹层特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"急性心包炎","aliases":[],"keyDiscriminator":"急性心包炎特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["持续胸痛伴大汗"],"fromExam":["血压偏低，心率偏快"],"fromTests":["心电图ST段抬高"]}},"treatment":{"immediate":[{"action":"双联抗血小板+抗凝","isCritical":true,"aliases":[]}],"definitive":[{"action":"急诊PCI再灌注","isCritical":true,"aliases":[]}],"dangerous":[{"action":"未稳定血流动力学即使用β阻滞剂","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_002', 'CC_CP_002', '急性胸痛 — 不稳定型心绞痛', 'chest_pain', 'cardiology', 'beginner', 15, '{"age":58,"presentationContext":"反复胸痛1天来诊"}'::jsonb, '{"chiefComplaint":"胸口闷痛反复发作","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["心音正常，无杂音"]}},"investigations":{"primary":{"result":"肌钙蛋白阴性，心电图ST-T改变"}}}'::jsonb, '{"diagnosis":{"primary":"不稳定型心绞痛","primaryAliases":["UA","不稳定心绞痛"],"icd10":"I20.0"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"胃食管反流病","aliases":[],"keyDiscriminator":"胃食管反流病特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["静息痛，活动加重"],"fromExam":["心音正常，无杂音"],"fromTests":["肌钙蛋白阴性，心电图ST-T改变"]}},"treatment":{"immediate":[{"action":"阿司匹林+硝酸甘油","isCritical":true,"aliases":[]}],"definitive":[{"action":"抗缺血治疗并评估血运重建","isCritical":true,"aliases":[]}],"dangerous":[{"action":"未排除心梗即出院","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_003', 'CC_CP_003', '急性胸痛 — 肺栓塞', 'chest_pain', 'respiratory', 'intermediate', 15, '{"age":42,"presentationContext":"术后突发胸痛、呼吸困难"}'::jsonb, '{"chiefComplaint":"突然胸痛还喘不上气","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["呼吸急促，血氧下降"]}},"investigations":{"primary":{"result":"D-二聚体升高，CTPA阳性"}}}'::jsonb, '{"diagnosis":{"primary":"急性肺栓塞","primaryAliases":["肺栓塞","PE"],"icd10":"I26.9"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"气胸","aliases":[],"keyDiscriminator":"气胸特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["术后卧床，突发呼吸困难"],"fromExam":["呼吸急促，血氧下降"],"fromTests":["D-二聚体升高，CTPA阳性"]}},"treatment":{"immediate":[{"action":"吸氧并抗凝","isCritical":true,"aliases":[]}],"definitive":[{"action":"根据风险分层选择抗凝或溶栓","isCritical":true,"aliases":[]}],"dangerous":[{"action":"高风险PE未抗凝","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_004', 'CC_CP_004', '急性胸痛 — 主动脉夹层', 'chest_pain', 'cardiology', 'advanced', 15, '{"age":55,"presentationContext":"撕裂样胸痛急诊就诊"}'::jsonb, '{"chiefComplaint":"胸口像被撕开一样疼","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["双上肢血压不对称"]}},"investigations":{"primary":{"result":"CTA显示夹层征象"}}}'::jsonb, '{"diagnosis":{"primary":"主动脉夹层","primaryAliases":["夹层","AD"],"icd10":"I71.0"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"急性心包炎","aliases":[],"keyDiscriminator":"急性心包炎特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["突发撕裂样胸背痛"],"fromExam":["双上肢血压不对称"],"fromTests":["CTA显示夹层征象"]}},"treatment":{"immediate":[{"action":"严格控制血压和心率","isCritical":true,"aliases":[]}],"definitive":[{"action":"根据分型选择手术或药物","isCritical":true,"aliases":[]}],"dangerous":[{"action":"夹层误用溶栓","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_005', 'CC_CP_005', '急性胸痛 — 气胸', 'chest_pain', 'respiratory', 'beginner', 15, '{"age":24,"presentationContext":"瘦高男性突发胸痛"}'::jsonb, '{"chiefComplaint":"一侧胸口突然刺痛","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["患侧呼吸音减弱"]}},"investigations":{"primary":{"result":"胸片见肺压缩线"}}}'::jsonb, '{"diagnosis":{"primary":"自发性气胸","primaryAliases":["气胸"],"icd10":"J93.9"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"肺栓塞","aliases":[],"keyDiscriminator":"肺栓塞特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["突发单侧胸痛"],"fromExam":["患侧呼吸音减弱"],"fromTests":["胸片见肺压缩线"]}},"treatment":{"immediate":[{"action":"吸氧并观察生命体征","isCritical":true,"aliases":[]}],"definitive":[{"action":"胸腔闭式引流","isCritical":true,"aliases":[]}],"dangerous":[{"action":"张力性气胸未减压","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_006', 'CC_CP_006', '急性胸痛 — 急性心包炎', 'chest_pain', 'cardiology', 'intermediate', 15, '{"age":36,"presentationContext":"发热后胸痛来诊"}'::jsonb, '{"chiefComplaint":"胸口疼，深呼吸更明显","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["心包摩擦音"]}},"investigations":{"primary":{"result":"心电图广泛导联ST抬高"}}}'::jsonb, '{"diagnosis":{"primary":"急性心包炎","primaryAliases":["心包炎"],"icd10":"I30.9"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"胸膜炎","aliases":[],"keyDiscriminator":"胸膜炎特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["近期病毒感染史"],"fromExam":["心包摩擦音"],"fromTests":["心电图广泛导联ST抬高"]}},"treatment":{"immediate":[{"action":"非甾体抗炎药","isCritical":true,"aliases":[]}],"definitive":[{"action":"针对病因治疗并随访","isCritical":true,"aliases":[]}],"dangerous":[{"action":"心包炎误溶栓","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_007', 'CC_CP_007', '急性胸痛 — 反流性食管炎', 'chest_pain', 'gastroenterology', 'beginner', 15, '{"age":48,"presentationContext":"餐后烧心样胸痛"}'::jsonb, '{"chiefComplaint":"吃完饭胸口烧灼痛","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["心肺查体无明显异常"]}},"investigations":{"primary":{"result":"心电图和肌钙蛋白正常"}}}'::jsonb, '{"diagnosis":{"primary":"反流性食管炎","primaryAliases":["胃食管反流","GERD"],"icd10":"K21.0"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"不稳定型心绞痛","aliases":[],"keyDiscriminator":"不稳定型心绞痛特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["餐后烧灼痛，平卧加重"],"fromExam":["心肺查体无明显异常"],"fromTests":["心电图和肌钙蛋白正常"]}},"treatment":{"immediate":[{"action":"质子泵抑制剂","isCritical":true,"aliases":[]}],"definitive":[{"action":"生活方式干预并评估反流","isCritical":true,"aliases":[]}],"dangerous":[{"action":"未排除ACS即按GERD处理","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_008', 'CC_CP_008', '急性胸痛 — 急性心肌炎', 'chest_pain', 'cardiology', 'intermediate', 15, '{"age":29,"presentationContext":"感冒后胸闷胸痛"}'::jsonb, '{"chiefComplaint":"感冒后胸口闷痛","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["心率增快，心音低钝"]}},"investigations":{"primary":{"result":"肌钙蛋白轻度升高，MRI心肌水肿"}}}'::jsonb, '{"diagnosis":{"primary":"急性心肌炎","primaryAliases":["心肌炎"],"icd10":"I40.9"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"心包炎","aliases":[],"keyDiscriminator":"心包炎特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["前驱病毒感染"],"fromExam":["心率增快，心音低钝"],"fromTests":["肌钙蛋白轻度升高，MRI心肌水肿"]}},"treatment":{"immediate":[{"action":"休息并监护心律","isCritical":true,"aliases":[]}],"definitive":[{"action":"支持治疗并评估心衰","isCritical":true,"aliases":[]}],"dangerous":[{"action":"心肌炎剧烈运动","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_009', 'CC_CP_009', '急性胸痛 — 肋软骨炎', 'chest_pain', 'general', 'beginner', 15, '{"age":33,"presentationContext":"局部压痛样胸痛"}'::jsonb, '{"chiefComplaint":"胸口某个点一按就疼","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["肋软骨压痛阳性"]}},"investigations":{"primary":{"result":"心电图和肌钙蛋白正常"}}}'::jsonb, '{"diagnosis":{"primary":"肋软骨炎","primaryAliases":["肋软骨炎","Tietze综合征"],"icd10":"M94.0"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"肺栓塞","aliases":[],"keyDiscriminator":"肺栓塞特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["局部压痛，与呼吸关系不大"],"fromExam":["肋软骨压痛阳性"],"fromTests":["心电图和肌钙蛋白正常"]}},"treatment":{"immediate":[{"action":"止痛对症处理","isCritical":true,"aliases":[]}],"definitive":[{"action":"观察并排除危重胸痛","isCritical":true,"aliases":[]}],"dangerous":[{"action":"未排除ACS即仅止痛","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_010', 'CC_CP_010', '急性胸痛 — 急性胰腺炎相关胸痛', 'chest_pain', 'gastroenterology', 'intermediate', 15, '{"age":52,"presentationContext":"上腹痛放射至胸部"}'::jsonb, '{"chiefComplaint":"上腹剧痛还扯到胸口","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["上腹压痛明显"]}},"investigations":{"primary":{"result":"血淀粉酶和脂肪酶升高"}}}'::jsonb, '{"diagnosis":{"primary":"急性胰腺炎","primaryAliases":["胰腺炎"],"icd10":"K85.9"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"主动脉夹层","aliases":[],"keyDiscriminator":"主动脉夹层特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["饮酒或高脂餐后上腹痛"],"fromExam":["上腹压痛明显"],"fromTests":["血淀粉酶和脂肪酶升高"]}},"treatment":{"immediate":[{"action":"禁食、补液、镇痛","isCritical":true,"aliases":[]}],"definitive":[{"action":"病因治疗并监护并发症","isCritical":true,"aliases":[]}],"dangerous":[{"action":"胰腺炎误溶栓","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_011', 'CC_CP_011', '急性胸痛 — 肺炎胸膜炎', 'chest_pain', 'respiratory', 'beginner', 15, '{"age":61,"presentationContext":"咳嗽发热伴胸痛"}'::jsonb, '{"chiefComplaint":"咳嗽时胸口更疼","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["语颤增强，呼吸音粗"]}},"investigations":{"primary":{"result":"胸片浸润影，白细胞升高"}}}'::jsonb, '{"diagnosis":{"primary":"肺炎伴胸膜炎","primaryAliases":["肺炎","胸膜炎"],"icd10":"J18.9"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"肺栓塞","aliases":[],"keyDiscriminator":"肺栓塞特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["咳嗽发热数天"],"fromExam":["语颤增强，呼吸音粗"],"fromTests":["胸片浸润影，白细胞升高"]}},"treatment":{"immediate":[{"action":"抗感染治疗","isCritical":true,"aliases":[]}],"definitive":[{"action":"根据病原学调整抗生素","isCritical":true,"aliases":[]}],"dangerous":[{"action":"重症肺炎未及时抗感染","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_012', 'CC_CP_012', '急性胸痛 — 焦虑相关胸痛', 'chest_pain', 'psychiatry', 'beginner', 15, '{"age":27,"presentationContext":"紧张后胸闷胸痛"}'::jsonb, '{"chiefComplaint":"一紧张就胸口发紧","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["查体无客观异常"]}},"investigations":{"primary":{"result":"心电图和肌钙蛋白正常"}}}'::jsonb, '{"diagnosis":{"primary":"焦虑相关胸痛","primaryAliases":["焦虑障碍","惊恐发作"],"icd10":"F41.9"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"不稳定型心绞痛","aliases":[],"keyDiscriminator":"不稳定型心绞痛特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["情绪诱发，持续时间短"],"fromExam":["查体无客观异常"],"fromTests":["心电图和肌钙蛋白正常"]}},"treatment":{"immediate":[{"action":"先排除ACS后安抚","isCritical":true,"aliases":[]}],"definitive":[{"action":"心理干预与随访","isCritical":true,"aliases":[]}],"dangerous":[{"action":"未排除ACS即诊断为焦虑","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_013', 'CC_CP_013', '急性胸痛 — 急性胆囊炎', 'chest_pain', 'general_surgery', 'intermediate', 15, '{"age":49,"presentationContext":"右上腹痛伴胸闷"}'::jsonb, '{"chiefComplaint":"右上腹疼还闷到胸口","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["Murphy征阳性"]}},"investigations":{"primary":{"result":"超声示胆囊结石并壁增厚"}}}'::jsonb, '{"diagnosis":{"primary":"急性胆囊炎","primaryAliases":["胆囊炎"],"icd10":"K81.0"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"下壁心肌梗死","aliases":[],"keyDiscriminator":"下壁心肌梗死特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["高脂餐后右上腹痛"],"fromExam":["Murphy征阳性"],"fromTests":["超声示胆囊结石并壁增厚"]}},"treatment":{"immediate":[{"action":"禁食、补液、抗感染","isCritical":true,"aliases":[]}],"definitive":[{"action":"评估手术时机","isCritical":true,"aliases":[]}],"dangerous":[{"action":"胆囊炎延误抗感染","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_014', 'CC_CP_014', '急性胸痛 — 急性心力衰竭', 'chest_pain', 'cardiology', 'intermediate', 15, '{"age":70,"presentationContext":"夜间憋醒伴胸痛"}'::jsonb, '{"chiefComplaint":"晚上喘不上气胸口也闷痛","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["双肺湿啰音，颈静脉怒张"]}},"investigations":{"primary":{"result":"BNP升高，胸片肺淤血"}}}'::jsonb, '{"diagnosis":{"primary":"急性心力衰竭","primaryAliases":["急性心衰","AHF"],"icd10":"I50.9"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"肺栓塞","aliases":[],"keyDiscriminator":"肺栓塞特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["端坐呼吸，夜间憋醒"],"fromExam":["双肺湿啰音，颈静脉怒张"],"fromTests":["BNP升高，胸片肺淤血"]}},"treatment":{"immediate":[{"action":"利尿、扩血管、氧疗","isCritical":true,"aliases":[]}],"definitive":[{"action":"明确诱因并优化心衰治疗","isCritical":true,"aliases":[]}],"dangerous":[{"action":"急性心衰误用β阻滞剂负荷剂量","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;

INSERT INTO case_templates (id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, demographics, patient_world, ground_truth, scoring_rubric, is_active, review_status, reviewed_by, reviewed_at) VALUES ('CC_CP_015', 'CC_CP_015', '急性胸痛 — 变异型心绞痛', 'chest_pain', 'cardiology', 'advanced', 15, '{"age":46,"presentationContext":"夜间静息胸痛发作"}'::jsonb, '{"chiefComplaint":"半夜胸口突然绞痛","history":{"presentIllness":[{"id":"onset","field":"起病","answer":"突然起病","patientVoice":"突然就开始不舒服了"},{"id":"site","field":"部位","answer":"与主诉相关部位","patientVoice":"就是现在说的这个地方"},{"id":"duration","field":"时长","answer":"数小时","patientVoice":"已经好几个小时了"}]},"physicalExam":{"general":{"findings":["发作间期查体可正常"]}},"investigations":{"primary":{"result":"发作时心电图ST段抬高"}}}'::jsonb, '{"diagnosis":{"primary":"变异型心绞痛","primaryAliases":["血管痉挛性心绞痛"],"icd10":"I20.1"},"differentials":[{"diagnosis":"急性心肌梗死","aliases":[],"keyDiscriminator":"急性心肌梗死特征","mustExclude":true,"supportAgainst":"不支持该诊断"},{"diagnosis":"胃食管反流病","aliases":[],"keyDiscriminator":"胃食管反流病特征","mustExclude":false,"supportAgainst":"需鉴别"}],"criticalEvidence":{"forDiagnosis":{"fromHistory":["静息夜间发作，活动不一定诱发"],"fromExam":["发作间期查体可正常"],"fromTests":["发作时心电图ST段抬高"]}},"treatment":{"immediate":[{"action":"硝酸甘油舌下含服","isCritical":true,"aliases":[]}],"definitive":[{"action":"钙通道阻滞剂并避免诱因","isCritical":true,"aliases":[]}],"dangerous":[{"action":"痉挛性心绞痛误用大剂量β阻滞剂","penalty":10,"aliases":[]}]}}'::jsonb, '{"diagnosis":{"weight":40,"exactMatch":40,"partialMatch":30,"categoryMatch":15,"hitDifferential":8,"wrong":0},"differential":{"weight":20,"threeOrMoreWithReasoning":20,"threeOrMore":16,"two":12,"one":8,"none":0,"missingCritical":-3},"evidence":{"weight":20,"coverageWeight":0.5,"associationWeight":0.3,"interpretationWeight":0.2},"treatment":{"weight":20,"criticalCoverageWeight":0.4,"safetyWeight":0.3,"reasonablenessWeight":0.3}}'::jsonb, true, 'approved', 'alpha-demo-medical-reviewer', '2026-06-13T00:00:00.000Z') ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, demographics = EXCLUDED.demographics, patient_world = EXCLUDED.patient_world, ground_truth = EXCLUDED.ground_truth, scoring_rubric = EXCLUDED.scoring_rubric, is_active = EXCLUDED.is_active, review_status = EXCLUDED.review_status, reviewed_by = EXCLUDED.reviewed_by, reviewed_at = EXCLUDED.reviewed_at;


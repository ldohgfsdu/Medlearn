CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id TEXT PRIMARY KEY,
    order_num INTEGER DEFAULT 0,
    type TEXT NOT NULL DEFAULT 'concept',
    title TEXT NOT NULL,
    subject TEXT,
    chapter TEXT,
    sub_chapter TEXT,
    knowledge_path TEXT[],
    content TEXT,
    key_points TEXT[] DEFAULT '{}',
    causal_links JSONB DEFAULT '[]',
    related_nodes TEXT[],
    difficulty INTEGER DEFAULT 1,
    tags TEXT[] DEFAULT '{}',
    source TEXT DEFAULT 'seed',
    book_id TEXT,
    textbook TEXT,
    edition TEXT,
    node_source TEXT,
    inferred BOOLEAN DEFAULT false,
    source_span JSONB,
    version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exam_questions (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'single',
    question TEXT NOT NULL,
    options TEXT[] NOT NULL,
    answer INTEGER NOT NULL,
    explanation TEXT,
    related_nodes TEXT[],
    difficulty INTEGER DEFAULT 1,
    source TEXT DEFAULT 'seed',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS causal_chains (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    steps JSONB NOT NULL DEFAULT '[]',
    related_nodes TEXT[],
    difficulty INTEGER DEFAULT 1,
    source TEXT DEFAULT 'seed',
    creator_user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    chief_complaint TEXT NOT NULL,
    stages JSONB DEFAULT '[]',
    difficulty INTEGER DEFAULT 1,
    related_nodes TEXT[],
    source TEXT DEFAULT 'seed',
    creator_user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nickname TEXT,
    avatar_url TEXT,
    preferences JSONB DEFAULT '{}',
    ai_config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feynman_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    transcript TEXT NOT NULL,
    ai_score JSONB NOT NULL DEFAULT '{}',
    feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dialogue_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    messages JSONB NOT NULL DEFAULT '[]',
    mastery_detected BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL REFERENCES cases(id),
    current_stage INTEGER DEFAULT 0,
    stage_scores JSONB DEFAULT '{}',
    total_score NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exam_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_ids TEXT[] NOT NULL,
    score NUMERIC DEFAULT 0,
    weak_nodes TEXT[],
    duration INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exam_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES exam_sessions(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES exam_questions(id),
    user_answer INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wrong_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES exam_questions(id),
    node_id TEXT REFERENCES knowledge_nodes(id),
    session_id UUID REFERENCES exam_sessions(id),
    retry_correct BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spaced_repetition (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    next_review TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    interval INTEGER DEFAULT 1,
    ease_factor NUMERIC DEFAULT 2.5,
    repetitions INTEGER DEFAULT 0,
    last_quality INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, node_id)
);

CREATE TABLE IF NOT EXISTS study_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    node_id TEXT REFERENCES knowledge_nodes(id),
    session_id UUID,
    record_id UUID,
    score NUMERIC,
    duration INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES knowledge_nodes(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, node_id)
);

CREATE TABLE IF NOT EXISTS learning_paths (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    node_ids TEXT[] DEFAULT '{}',
    progress NUMERIC DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS study_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    goals JSONB DEFAULT '[]',
    schedule JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS study_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    target NUMERIC NOT NULL,
    current NUMERIC DEFAULT 0,
    period TEXT NOT NULL DEFAULT 'daily',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_subject ON knowledge_nodes(subject);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_type ON knowledge_nodes(type);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_chapter ON knowledge_nodes(chapter);
CREATE INDEX IF NOT EXISTS idx_feynman_records_user ON feynman_records(user_id);
CREATE INDEX IF NOT EXISTS idx_feynman_records_node ON feynman_records(node_id);
CREATE INDEX IF NOT EXISTS idx_feynman_records_user_node ON feynman_records(user_id, node_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_records_user ON dialogue_records(user_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_records_node ON dialogue_records(node_id);
CREATE INDEX IF NOT EXISTS idx_case_records_user ON case_records(user_id);
CREATE INDEX IF NOT EXISTS idx_case_records_case ON case_records(case_id);
CREATE INDEX IF NOT EXISTS idx_exam_records_user ON exam_records(user_id);
CREATE INDEX IF NOT EXISTS idx_exam_records_session ON exam_records(session_id);
CREATE INDEX IF NOT EXISTS idx_exam_sessions_user ON exam_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_wrong_questions_user ON wrong_questions(user_id);
CREATE INDEX IF NOT EXISTS idx_wrong_questions_question ON wrong_questions(question_id);
CREATE INDEX IF NOT EXISTS idx_spaced_repetition_user ON spaced_repetition(user_id);
CREATE INDEX IF NOT EXISTS idx_spaced_repetition_next_review ON spaced_repetition(user_id, next_review);
CREATE INDEX IF NOT EXISTS idx_spaced_repetition_node ON spaced_repetition(user_id, node_id);
CREATE INDEX IF NOT EXISTS idx_study_activities_user ON study_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_study_activities_type ON study_activities(user_id, type);
CREATE INDEX IF NOT EXISTS idx_study_activities_created ON study_activities(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_study_goals_user ON study_goals(user_id);

ALTER TABLE knowledge_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE causal_chains ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
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

CREATE POLICY "Allow public read" ON knowledge_nodes FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON exam_questions FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON causal_chains FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON cases FOR SELECT USING (true);

CREATE POLICY "Users can view own profile" ON user_profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON user_profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Users can insert own profile" ON user_profiles FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can view own feynman records" ON feynman_records FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own feynman records" ON feynman_records FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own feynman records" ON feynman_records FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own feynman records" ON feynman_records FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own dialogue records" ON dialogue_records FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own dialogue records" ON dialogue_records FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own dialogue records" ON dialogue_records FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own dialogue records" ON dialogue_records FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own case records" ON case_records FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own case records" ON case_records FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own case records" ON case_records FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own case records" ON case_records FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own exam records" ON exam_records FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own exam records" ON exam_records FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own exam sessions" ON exam_sessions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own exam sessions" ON exam_sessions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own exam sessions" ON exam_sessions FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own wrong questions" ON wrong_questions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own wrong questions" ON wrong_questions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own wrong questions" ON wrong_questions FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own wrong questions" ON wrong_questions FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own spaced repetition" ON spaced_repetition FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own spaced repetition" ON spaced_repetition FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own spaced repetition" ON spaced_repetition FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own spaced repetition" ON spaced_repetition FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own study activities" ON study_activities FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own study activities" ON study_activities FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own favorites" ON favorites FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own favorites" ON favorites FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete own favorites" ON favorites FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own learning paths" ON learning_paths FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own learning paths" ON learning_paths FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own learning paths" ON learning_paths FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own learning paths" ON learning_paths FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own study plans" ON study_plans FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own study plans" ON study_plans FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own study plans" ON study_plans FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own study plans" ON study_plans FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own study goals" ON study_goals FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own study goals" ON study_goals FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own study goals" ON study_goals FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own study goals" ON study_goals FOR DELETE USING (auth.uid() = user_id);

CREATE OR REPLACE VIEW user_learning_stats AS
SELECT
    user_id,
    COUNT(*) FILTER (WHERE type = 'feynman') AS feynman_count,
    COUNT(*) FILTER (WHERE type = 'exam') AS exam_count,
    COUNT(*) FILTER (WHERE type = 'pathway') AS pathway_count,
    COUNT(*) FILTER (WHERE type = 'case') AS case_count,
    COALESCE(SUM(duration), 0) AS total_duration,
    COUNT(DISTINCT DATE(created_at)) AS study_days
FROM study_activities
GROUP BY user_id;

CREATE OR REPLACE VIEW node_mastery AS
SELECT
    fr.user_id,
    fr.node_id,
    kn.title AS node_title,
    kn.subject,
    AVG((fr.ai_score->>'accuracy')::NUMERIC) AS avg_accuracy,
    AVG((fr.ai_score->>'completeness')::NUMERIC) AS avg_completeness,
    AVG((fr.ai_score->>'clarity')::NUMERIC) AS avg_clarity,
    AVG((fr.ai_score->>'depth')::NUMERIC) AS avg_depth,
    COUNT(*) AS attempt_count,
    MAX(fr.created_at) AS last_attempt
FROM feynman_records fr
JOIN knowledge_nodes kn ON kn.id = fr.node_id
GROUP BY fr.user_id, fr.node_id, kn.title, kn.subject;

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_knowledge_nodes_updated_at BEFORE UPDATE ON knowledge_nodes FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_exam_questions_updated_at BEFORE UPDATE ON exam_questions FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_causal_chains_updated_at BEFORE UPDATE ON causal_chains FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_cases_updated_at BEFORE UPDATE ON cases FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_user_profiles_updated_at BEFORE UPDATE ON user_profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_case_records_updated_at BEFORE UPDATE ON case_records FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_exam_sessions_updated_at BEFORE UPDATE ON exam_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_wrong_questions_updated_at BEFORE UPDATE ON wrong_questions FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_spaced_repetition_updated_at BEFORE UPDATE ON spaced_repetition FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_learning_paths_updated_at BEFORE UPDATE ON learning_paths FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_study_plans_updated_at BEFORE UPDATE ON study_plans FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_study_goals_updated_at BEFORE UPDATE ON study_goals FOR EACH ROW EXECUTE FUNCTION update_updated_at();

INSERT INTO knowledge_nodes (id, title, type, subject, chapter, sub_chapter, content, key_points, difficulty, order_num, textbook) VALUES
('k001', '心力衰竭', 'disease', '内科学', '第四篇 循环系统疾病', '第一章 心力衰竭', '心力衰竭是各种心脏结构或功能性疾病导致心室充盈和（或）射血功能受损，心排血量不能满足机体组织代谢需要，以肺循环和（或）体循环淤血，器官、组织血液灌注不足为临床表现的一组综合征。', ARRAY['心排血量下降', '肺循环淤血', '体循环淤血', '组织灌注不足'], 2, 0, '内科学'),
('k002', '高血压', 'disease', '内科学', '第四篇 循环系统疾病', '第二章 原发性高血压', '高血压是以体循环动脉压升高为主要临床表现的心血管综合征，可分为原发性高血压和继发性高血压。', ARRAY['收缩压≥140mmHg', '舒张压≥90mmHg', '靶器官损害', '心血管风险分层'], 1, 1, '内科学'),
('k003', '肺炎', 'disease', '内科学', '第一篇 呼吸系统疾病', '第三章 肺部感染性疾病', '肺炎是指终末气道、肺泡和肺间质的炎症，可由病原微生物、理化因素、免疫损伤、过敏及药物所致。', ARRAY['发热', '咳嗽咳痰', '肺部湿啰音', '胸片浸润影'], 1, 2, '内科学'),
('k004', '糖尿病', 'disease', '内科学', '第七篇 内分泌和代谢疾病', '第一章 糖尿病', '糖尿病是由多病因引起以慢性高血糖为特征的代谢性疾病，是由于胰岛素分泌和（或）利用缺陷所引起。', ARRAY['多饮多尿多食', '血糖升高', '糖化血红蛋白', '并发症筛查'], 2, 3, '内科学'),
('k005', '冠心病', 'disease', '内科学', '第四篇 循环系统疾病', '第三章 冠状动脉粥样硬化性心脏病', '冠状动脉粥样硬化性心脏病是指冠状动脉发生粥样硬化引起管腔狭窄或闭塞，导致心肌缺血缺氧或坏死而引起的心脏病。', ARRAY['胸痛', '心电图改变', '冠脉造影', '血运重建'], 2, 4, '内科学')
ON CONFLICT (id) DO NOTHING;

INSERT INTO exam_questions (id, type, question, options, answer, explanation, difficulty) VALUES
('q001', 'single', '心力衰竭最常见的诱因是？', ARRAY['感染', '心律失常', '血容量增加', '过度劳累'], 0, '感染是心力衰竭最常见的诱因，尤其是呼吸道感染。', 1),
('q002', 'single', '高血压的诊断标准是收缩压≥多少mmHg？', ARRAY['130', '140', '150', '160'], 1, '高血压诊断标准：收缩压≥140mmHg和（或）舒张压≥90mmHg。', 1),
('q003', 'single', '2型糖尿病的主要发病机制是？', ARRAY['胰岛素分泌不足', '胰岛素抵抗', '胰岛β细胞破坏', '遗传因素'], 1, '2型糖尿病主要以胰岛素抵抗为主，伴胰岛素分泌不足。', 2)
ON CONFLICT (id) DO NOTHING;

INSERT INTO cases (id, title, chief_complaint, stages, difficulty) VALUES
('c001', '心力衰竭病例', '活动后气促2年，加重1周',
 '[{"stage_num":0,"title":"病史采集","content":"患者男性，65岁，活动后气促2年，近1周加重，夜间不能平卧。既往有高血压病史10年。","choices":[{"text":"详细询问胸痛特点"},{"text":"了解用药史"},{"text":"询问夜间阵发性呼吸困难"},{"text":"以上都需要"}],"correct_answer":3,"explanation":"心力衰竭的诊断需要综合病史、症状、体征和辅助检查。"},{"stage_num":1,"title":"体格检查","content":"查体：BP 150/90mmHg，双肺底可闻及湿啰音，心界向左下扩大，心率100次/分，双下肢凹陷性水肿。","choices":[{"text":"心力衰竭"},{"text":"肺炎"},{"text":"支气管哮喘"},{"text":"肺栓塞"}],"correct_answer":0,"explanation":"结合病史和体征，考虑心力衰竭诊断。"}]',
 2)
ON CONFLICT (id) DO NOTHING;

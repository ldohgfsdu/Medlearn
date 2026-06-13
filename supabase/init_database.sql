-- Medlearn 数据库初始化脚本
-- ⚠️ 已废弃：请使用 supabase/migrations/ 下的增量迁移脚本
-- 本文件仅作参考，不应再用于实际部署

-- 1. 知识点表
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    type TEXT DEFAULT 'concept',
    subject TEXT,
    chapter TEXT,
    sub_chapter TEXT,
    level INTEGER DEFAULT 3,
    content TEXT,
    key_points TEXT[] DEFAULT '{}',
    difficulty INTEGER DEFAULT 1,
    tags TEXT[] DEFAULT '{}',
    order_num INTEGER DEFAULT 0,
    textbook TEXT,
    source TEXT DEFAULT 'seed',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 考试题目表
CREATE TABLE IF NOT EXISTS exam_questions (
    id TEXT PRIMARY KEY,
    type TEXT DEFAULT 'single',
    question TEXT NOT NULL,
    options TEXT[] NOT NULL,
    answer INTEGER NOT NULL,
    explanation TEXT,
    difficulty INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 病例表
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    chief_complaint TEXT NOT NULL,
    stages JSONB DEFAULT '[]',
    difficulty INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 插入测试知识点
-- subject=教材, chapter=篇, sub_chapter=章, level=2(章级)或3(知识点)
INSERT INTO knowledge_nodes (id, title, type, subject, chapter, sub_chapter, level, content, key_points, difficulty, order_num, textbook) VALUES
('k001', '心力衰竭', 'disease', '内科学', '第四篇 循环系统疾病', '第一章 心力衰竭', 3,
 '心力衰竭是各种心脏结构或功能性疾病导致心室充盈和（或）射血功能受损，心排血量不能满足机体组织代谢需要，以肺循环和（或）体循环淤血，器官、组织血液灌注不足为临床表现的一组综合征。',
 ARRAY['心排血量下降', '肺循环淤血', '体循环淤血', '组织灌注不足'],
 2, 0, '内科学'),
 
('k002', '高血压', 'disease', '内科学', '第四篇 循环系统疾病', '第二章 原发性高血压', 3,
 '高血压是以体循环动脉压升高为主要临床表现的心血管综合征，可分为原发性高血压和继发性高血压。',
 ARRAY['收缩压≥140mmHg', '舒张压≥90mmHg', '靶器官损害', '心血管风险分层'],
 1, 1, '内科学'),
 
('k003', '肺炎', 'disease', '内科学', '第一篇 呼吸系统疾病', '第三章 肺部感染性疾病', 3,
 '肺炎是指终末气道、肺泡和肺间质的炎症，可由病原微生物、理化因素、免疫损伤、过敏及药物所致。',
 ARRAY['发热', '咳嗽咳痰', '肺部湿啰音', '胸片浸润影'],
 1, 2, '内科学'),
 
('k004', '糖尿病', 'disease', '内科学', '第七篇 内分泌和代谢疾病', '第一章 糖尿病', 3,
 '糖尿病是由多病因引起以慢性高血糖为特征的代谢性疾病，是由于胰岛素分泌和（或）利用缺陷所引起。',
 ARRAY['多饮多尿多食', '血糖升高', '糖化血红蛋白', '并发症筛查'],
 2, 3, '内科学'),
 
('k005', '冠心病', 'disease', '内科学', '第四篇 循环系统疾病', '第三章 冠状动脉粥样硬化性心脏病', 3,
 '冠状动脉粥样硬化性心脏病是指冠状动脉发生粥样硬化引起管腔狭窄或闭塞，导致心肌缺血缺氧或坏死而引起的心脏病。',
 ARRAY['胸痛', '心电图改变', '冠脉造影', '血运重建'],
 2, 4, '内科学');

-- 5. 插入测试题目
INSERT INTO exam_questions (id, type, question, options, answer, explanation, difficulty) VALUES
('q001', 'single', '心力衰竭最常见的诱因是？', 
 ARRAY['感染', '心律失常', '血容量增加', '过度劳累'], 
 0, '感染是心力衰竭最常见的诱因，尤其是呼吸道感染。', 1),
 
('q002', 'single', '高血压的诊断标准是收缩压≥多少mmHg？', 
 ARRAY['130', '140', '150', '160'], 
 1, '高血压诊断标准：收缩压≥140mmHg和（或）舒张压≥90mmHg。', 1),
 
('q003', 'single', '2型糖尿病的主要发病机制是？', 
 ARRAY['胰岛素分泌不足', '胰岛素抵抗', '胰岛β细胞破坏', '遗传因素'], 
 1, '2型糖尿病主要以胰岛素抵抗为主，伴胰岛素分泌不足。', 2);

-- 6. 插入测试病例
INSERT INTO cases (id, title, chief_complaint, stages, difficulty) VALUES
('c001', '心力衰竭病例', '活动后气促2年，加重1周',
 '[
   {"stage_num": 0, "title": "病史采集", "content": "患者男性，65岁，活动后气促2年，近1周加重，夜间不能平卧。既往有高血压病史10年。", "choices": [{"text": "详细询问胸痛特点"}, {"text": "了解用药史"}, {"text": "询问夜间阵发性呼吸困难"}, {"text": "以上都需要"}], "correct_answer": 3, "explanation": "心力衰竭的诊断需要综合病史、症状、体征和辅助检查。"},
   {"stage_num": 1, "title": "体格检查", "content": "查体：BP 150/90mmHg，双肺底可闻及湿啰音，心界向左下扩大，心率100次/分，双下肢凹陷性水肿。", "choices": [{"text": "心力衰竭"}, {"text": "肺炎"}, {"text": "支气管哮喘"}, {"text": "肺栓塞"}], "correct_answer": 0, "explanation": "结合病史和体征，考虑心力衰竭诊断。"}
 ]',
 2);

-- 7. 启用 RLS（行级安全）
ALTER TABLE knowledge_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;

-- 8. 创建公开读取策略
CREATE POLICY "Allow public read" ON knowledge_nodes FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON exam_questions FOR SELECT USING (true);
CREATE POLICY "Allow public read" ON cases FOR SELECT USING (true);

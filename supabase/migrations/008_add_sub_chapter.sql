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

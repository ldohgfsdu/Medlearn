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

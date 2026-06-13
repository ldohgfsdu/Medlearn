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

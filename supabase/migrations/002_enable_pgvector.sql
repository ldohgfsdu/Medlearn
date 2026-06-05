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
    embedding VECTOR(384),                 -- 向量（可选，用于语义检索）
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
    WITH (lists = 100);

-- ============================================
-- 4. 创建向量检索函数
-- ============================================

-- 相似度检索函数
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(384),
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
    query_embedding VECTOR(384),
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

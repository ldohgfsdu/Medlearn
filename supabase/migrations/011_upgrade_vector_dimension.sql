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

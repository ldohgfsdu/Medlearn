-- V4.7.0a Structure Validation
-- knowledge_chapters: 负责教材目录树（Display Hierarchy）
-- 永远不要和 knowledge_relations 混用

CREATE TABLE IF NOT EXISTS knowledge_chapters (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    book_id text NOT NULL,
    title text NOT NULL,
    order_index int NOT NULL,
    parent_id uuid REFERENCES knowledge_chapters(id),
    level int NOT NULL, -- 1=book, 2=chapter, 3=section
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    
    UNIQUE(book_id, title, level)
);

-- Index for fast hierarchy traversal
CREATE INDEX idx_chapters_book ON knowledge_chapters(book_id);
CREATE INDEX idx_chapters_parent ON knowledge_chapters(parent_id);
CREATE INDEX idx_chapters_order ON knowledge_chapters(order_index);

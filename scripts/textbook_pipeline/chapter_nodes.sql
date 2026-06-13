-- V4.7.0a Structure Validation
-- chapter_nodes: 负责「章节」和「知识点」的 display 关系
-- 这是 display hierarchy，不是 semantic relation

CREATE TABLE IF NOT EXISTS chapter_nodes (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    chapter_id uuid NOT NULL REFERENCES knowledge_chapters(id),
    knowledge_point_id uuid NOT NULL REFERENCES knowledge_points(id),
    display_order int NOT NULL,
    created_at timestamptz DEFAULT now(),
    
    UNIQUE(chapter_id, knowledge_point_id),
    UNIQUE(chapter_id, display_order)
);

-- Index for fast chapter reconstruction
CREATE INDEX idx_chapter_nodes_chapter ON chapter_nodes(chapter_id);
CREATE INDEX idx_chapter_nodes_point ON chapter_nodes(knowledge_point_id);
CREATE INDEX idx_chapter_nodes_order ON chapter_nodes(display_order);

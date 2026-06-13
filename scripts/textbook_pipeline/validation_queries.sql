-- V4.7.0a Structure Validation Queries
-- Run these after ingestion to validate structure

-- 1. Orphan nodes (knowledge point without any chapter)
SELECT 
    kp.title,
    kp.type
FROM knowledge_points kp
LEFT JOIN chapter_nodes cn ON cn.knowledge_point_id = kp.id
WHERE cn.knowledge_point_id IS NULL
ORDER BY kp.title;

-- 2. Duplicate chapter assignment
SELECT 
    knowledge_point_id,
    count(*) as chapter_count
FROM chapter_nodes
GROUP BY knowledge_point_id
HAVING count(*) > 1;

-- 3. Duplicate display_order in same chapter
SELECT 
    chapter_id,
    display_order,
    count(*) as duplicate_count
FROM chapter_nodes
GROUP BY chapter_id, display_order
HAVING count(*) > 1;

-- 4. Chapter hierarchy integrity
SELECT 
    c1.title as child,
    c2.title as parent
FROM knowledge_chapters c1
LEFT JOIN knowledge_chapters c2 ON c1.parent_id = c2.id
WHERE c1.level > 1 AND c2.id IS NULL;

-- 5. Can we reconstruct full book?
WITH RECURSIVE chapter_tree AS (
    SELECT id, title, parent_id, order_index, 1 as level
    FROM knowledge_chapters
    WHERE parent_id IS NULL
    UNION ALL
    SELECT c.id, c.title, c.parent_id, c.order_index, ct.level + 1
    FROM knowledge_chapters c
    JOIN chapter_tree ct ON c.parent_id = ct.id
)
SELECT 
    title,
    level,
    order_index
FROM chapter_tree
ORDER BY level, order_index;

-- 6. Can we export a chapter?
SELECT 
    kc.title as chapter,
    kp.title as knowledge_point,
    kp.type,
    cn.display_order
FROM chapter_nodes cn
JOIN knowledge_chapters kc ON kc.id = cn.chapter_id
JOIN knowledge_points kp ON kp.id = cn.knowledge_point_id
WHERE kc.title = '呼吸系统疾病'
ORDER BY cn.display_order;

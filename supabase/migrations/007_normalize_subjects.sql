-- 数据规范化：确保 subject=教材名，chapter=篇，sub_chapter=章
-- Created: 2026-06-06

-- 1. 将 subject 为"篇"级标题的记录统一归入教材名
UPDATE knowledge_nodes
SET subject = '内科学'
WHERE subject LIKE '第%篇%'
   OR subject LIKE '第%部分%'
   OR subject LIKE '第%章%';

-- 2. 如果 chapter 是 "篇 > 章" 格式，拆分到 chapter 和 sub_chapter
-- 例如: chapter="第一篇 呼吸系统疾病 > 第一章 感冒" → chapter="第一篇 呼吸系统疾病", sub_chapter="第一章 感冒"
UPDATE knowledge_nodes
SET chapter = SPLIT_PART(chapter, ' > ', 1),
    sub_chapter = SPLIT_PART(chapter, ' > ', 2)
WHERE chapter LIKE '% > %';

-- 3. 补全旧种子数据（没有 chapter 的）
-- 按知识点标题自动归入对应篇
UPDATE knowledge_nodes SET chapter = '第四篇 循环系统疾病', sub_chapter = '第一章 心力衰竭'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '心力衰竭';

UPDATE knowledge_nodes SET chapter = '第四篇 循环系统疾病', sub_chapter = '第二章 原发性高血压'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '高血压';

UPDATE knowledge_nodes SET chapter = '第四篇 循环系统疾病', sub_chapter = '第三章 冠状动脉粥样硬化性心脏病'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '冠心病';

UPDATE knowledge_nodes SET chapter = '第一篇 呼吸系统疾病', sub_chapter = '第三章 肺部感染性疾病'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '肺炎';

UPDATE knowledge_nodes SET chapter = '第七篇 内分泌和代谢疾病', sub_chapter = '第一章 糖尿病'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '' OR chapter = '其他')
  AND title = '糖尿病';

-- 剩余未归类的统一放入"其他"
UPDATE knowledge_nodes SET chapter = '其他'
WHERE subject = '内科学' AND (chapter IS NULL OR chapter = '');

-- 4. 确保 order_num、textbook、level 字段存在
ALTER TABLE knowledge_nodes ALTER COLUMN order_num SET DEFAULT 0;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS textbook TEXT;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 3;

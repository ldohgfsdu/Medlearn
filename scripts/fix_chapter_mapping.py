"""读取 PDF TOC，生成修复 chapter 字段的 SQL"""
import os
import fitz
from collections import defaultdict

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)

doc = fitz.open(os.path.join(_project_root, 'textbook', '内科学（第10版）.pdf'))
toc = doc.get_toc()

part = ''
mapping = {}  # chapter_name -> part_name

for lvl, title, page in toc:
    t = title.replace('\n', '').strip()
    if lvl == 1:
        part = t
    elif lvl == 2 and part:
        mapping[t] = part

# 按篇分组
by_part = defaultdict(list)
for ch, pt in mapping.items():
    by_part[pt].append(ch)

# 生成 SQL
lines = [
    '-- 自动生成：按内科学 TOC 目录修复 chapter 字段',
    '-- 在 Supabase SQL Editor 中运行',
    '-- 此 SQL 将 chapter=章名 的记录更新为 chapter=篇名',
    '',
    '-- 同时确保 sub_chapter 存在章名',
]

for part_name in sorted(by_part.keys()):
    chapters = by_part[part_name]
    ch_list = ', '.join([f"'{c.replace(chr(39), chr(39)*2)}'" for c in chapters])
    lines.append(f"UPDATE knowledge_nodes SET chapter = '{part_name.replace(chr(39), chr(39)*2)}' WHERE sub_chapter IN ({ch_list});")

lines.append('')
lines.append('-- 如果 sub_chapter 为空但 chapter 是章名，用 chapter 作为 sub_chapter')
lines.append("UPDATE knowledge_nodes SET sub_chapter = chapter WHERE sub_chapter IS NULL AND chapter LIKE '第%章%';")
lines.append("UPDATE knowledge_nodes SET chapter = '其他' WHERE chapter IS NULL OR chapter = '';")

sql = '\n'.join(lines)

# 写入文件
with open(os.path.join(_project_root, 'supabase', 'migrations', '009_fix_chapter_mapping.sql'), 'w', encoding='utf-8') as f:
    f.write(sql)

print(f'✅ 生成 {len(by_part)} 个篇的映射，共 {len(mapping)} 个章')
print(f'   已写入 supabase/migrations/009_fix_chapter_mapping.sql')
print()
print('前5条映射:')
for pt in sorted(by_part.keys())[:5]:
    print(f'  {pt}: {", ".join(by_part[pt][:3])}...')

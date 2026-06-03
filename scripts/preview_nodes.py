import json
from pathlib import Path
from collections import Counter

nodes_file = Path('generated/textbook/physiology-10-v9/nodes.staging.json')
data = json.loads(nodes_file.read_text(encoding='utf-8'))
nodes = data['nodes']

print(f'📚 生理学（第10版）解析结果预览')
print(f'{"=" * 70}')
print(f'总计: {len(nodes)} 个知识点')
print()

type_counts = Counter(n['type'] for n in nodes)
print('📊 类型分布:')
for t, c in type_counts.most_common():
    print(f'  {t}: {c} 个')
print()

chapters = Counter(n.get('chapter', '未知') for n in nodes)
print('📖 章节分布:')
for ch, c in chapters.most_common():
    print(f'  {ch}: {c} 个知识点')
print()

print('📋 知识点列表:')
print('-' * 70)
for i, n in enumerate(nodes):
    page = n['sourceSpan']['pageStart']
    chapter = n.get('chapter', '未知')
    print(f'{i+1:2d}. [{chapter}] {n["title"]:<35} ({n["type"]:<10}) 第{page}页')

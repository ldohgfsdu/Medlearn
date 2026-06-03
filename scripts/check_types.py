import json
from pathlib import Path
from collections import Counter

nodes_file = Path('generated/textbook/physiology-10-v13/nodes.staging.json')
data = json.loads(nodes_file.read_text(encoding='utf-8'))
nodes = data['nodes']

print('=== 生理学知识点类型分布 ===')
print()

type_counts = Counter(n['type'] for n in nodes)
for t, c in type_counts.most_common():
    print(f'  {t}: {c} 个')

print()
print('=== 检查是否有错误的 disease 类型 ===')
disease_nodes = [n for n in nodes if n['type'] == 'disease']
if disease_nodes:
    print(f'发现 {len(disease_nodes)} 个 disease 类型:')
    for n in disease_nodes[:5]:
        print(f'  - {n["title"]}')
else:
    print('没有 disease 类型，正确！')

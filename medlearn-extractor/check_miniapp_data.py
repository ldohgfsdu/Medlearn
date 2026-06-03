import json
import os

# 检查小程序中的JSON数据文件
data_dirs = [
    'g:/MedLearn/mini-program/pagesA/data',
    'g:/MedLearn/mini-program/pagesB/data',
    'g:/MedLearn/mini-program/pagesC/data',
]

total_nodes = 0
files_info = []

for data_dir in data_dirs:
    if not os.path.exists(data_dir):
        continue
    for f in os.listdir(data_dir):
        if f.endswith('.json'):
            filepath = os.path.join(data_dir, f)
            with open(filepath, 'r', encoding='utf-8') as file:
                nodes = json.load(file)
                total_nodes += len(nodes)
                files_info.append((f, len(nodes)))
                print(f'{f}: {len(nodes)} 个知识点')

print(f'\n=== 小程序数据统计 ===')
print(f'总知识点数: {total_nodes}')

# 检查knowledgeIndex
with open('g:/MedLearn/mini-program/src/data/knowledgeIndex.ts', 'r', encoding='utf-8') as f:
    content = f.read()
    # 统计数组中的元素数量
    import re
    match = re.search(r'export const knowledgeIndex: KnowledgeNodeIndex\[\] = (\[[\s\S]*?\]);', content)
    if match:
        nodes = json.loads(match.group(1))
        print(f'knowledgeIndex 中的知识点数: {len(nodes)}')

import json
from pathlib import Path

nodes_file = Path('generated/textbook/physiology-10-v11/nodes.staging.json')
data = json.loads(nodes_file.read_text(encoding='utf-8'))
nodes = data['nodes']

print('=== 内容质量问题分析 ===')
print()

for i, n in enumerate(nodes[:5]):
    print(f'知识点 {i+1}: {n["title"]}')
    print(f'  内容长度: {len(n["content"])} 字符')
    print(f'  keyPoints: {len(n["keyPoints"])} 个')
    print(f'  章节: {n["chapter"]}')
    print()
    print('  内容开头 (前150字符):')
    print('  ' + '-' * 40)
    print('  ' + n['content'][:150].replace('\n', '\n  '))
    print('  ' + '-' * 40)
    print()

print('=== 统计 ===')
total_content = sum(len(n['content']) for n in nodes)
empty_keypoints = sum(1 for n in nodes if len(n['keyPoints']) == 0)
print(f'总知识点: {len(nodes)}')
print(f'总内容量: {total_content} 字符')
print(f'平均内容: {total_content // len(nodes)} 字符/知识点')
print(f'空keyPoints: {empty_keypoints} 个')

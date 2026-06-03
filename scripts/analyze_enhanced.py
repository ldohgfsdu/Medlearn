import json
from pathlib import Path

nodes_file = Path('generated/textbook/physiology-10-v12/nodes.staging.json')
data = json.loads(nodes_file.read_text(encoding='utf-8'))
nodes = data['nodes']

print('=== 增强版知识点分析 ===')
print()

for i, n in enumerate(nodes[10:15]):
    print(f'知识点 {i+11}: {n["title"]}')
    print(f'  章节: {n["chapter"]}')
    print(f'  类型: {n["type"]}')
    print(f'  定义: {n.get("definition", "无")[:100]}...' if n.get('definition') else '  定义: 无')
    print(f'  keyPoints: {len(n.get("keyPoints", []))} 个')
    print(f'  qaPairs: {len(n.get("qaPairs", []))} 个')
    if n.get('qaPairs'):
        for qa in n['qaPairs'][:2]:
            print(f'    Q: {qa["question"][:50]}...')
            print(f'    A: {qa["answer"][:50]}...')
    print()

print('=== 统计 ===')
total_nodes = len(nodes)
nodes_with_def = sum(1 for n in nodes if n.get('definition'))
nodes_with_kp = sum(1 for n in nodes if n.get('keyPoints'))
nodes_with_qa = sum(1 for n in nodes if n.get('qaPairs'))
total_qa = sum(len(n.get('qaPairs', [])) for n in nodes)

print(f'总知识点: {total_nodes}')
print(f'有定义: {nodes_with_def} ({nodes_with_def*100//total_nodes}%)')
print(f'有keyPoints: {nodes_with_kp} ({nodes_with_kp*100//total_nodes}%)')
print(f'有问答对: {nodes_with_qa} ({nodes_with_qa*100//total_nodes}%)')
print(f'总问答对: {total_qa}')

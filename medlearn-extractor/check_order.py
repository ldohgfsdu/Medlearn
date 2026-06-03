import json
import re

# 读取seedKnowledgeNodes.ts
with open('g:/MedLearn/mini-program/src/data/seedKnowledgeNodes.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JSON
match = re.search(r'export const seedKnowledgeNodes: KnowledgeNode\[\] = (\[[\s\S]*?\]);', content)
if match:
    nodes = json.loads(match.group(1))
    
    # 检查呼吸系统的顺序
    respiratory_nodes = [n for n in nodes if '呼吸' in n.get('subject', '')]
    print('=== 呼吸系统知识点顺序 ===')
    for i, node in enumerate(respiratory_nodes[:15]):
        order = node.get('order', 'N/A')
        title = node['title']
        chapter = node.get('chapter', 'N/A')
        print(f"{order}: {title} - {chapter}")

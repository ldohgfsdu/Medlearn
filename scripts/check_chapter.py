import json
from pathlib import Path

nodes_file = Path('public/extracted-knowledge.json')
nodes = json.loads(nodes_file.read_text(encoding='utf-8'))

print('=== 检查慢性支气管炎的 chapter 字段 ===')
for n in nodes:
    if '慢性支气管炎' in n.get('title', ''):
        print(f"title: {n['title']}")
        print(f"chapter: {n.get('chapter')}")
        print(f"subject: {n.get('subject')}")
        print(f"type: {n.get('type')}")
        print()

print('=== 检查急性上呼吸道感染的 chapter 字段 ===')
for n in nodes:
    if '急性上呼吸道感染' in n.get('title', '') and '急性气管' not in n.get('title', ''):
        print(f"title: {n['title']}")
        print(f"chapter: {n.get('chapter')}")
        print(f"subject: {n.get('subject')}")
        print()

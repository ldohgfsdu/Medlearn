import json

with open('output/structured.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

kps = data.get('knowledge_points', [])

print("=== 失败的知识点 ===\n")
for kp in kps:
    status = kp.get('structurize_status', '')
    if status.startswith('error'):
        print(f"名称: {kp['name']}")
        print(f"系统: {kp.get('_system', 'N/A')}")
        print(f"章: {kp.get('_chapter', 'N/A')}")
        print(f"错误: {status}")
        print('---')

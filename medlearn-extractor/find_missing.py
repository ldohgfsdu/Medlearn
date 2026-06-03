import json

# 读取structured.json
with open('g:/MedLearn/medlearn-extractor/output/structured.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

kps = data.get('knowledge_points', [])

# 读取小程序的respiratory.json
with open('g:/MedLearn/mini-program/pagesB/data/respiratory.json', 'r', encoding='utf-8') as f:
    respiratory_nodes = json.load(f)

# 获取小程序中的知识点ID
miniapp_ids = set(node['id'] for node in respiratory_nodes)

print('=== 呼吸系统遗漏的知识点 ===')
missing = []
for kp in kps:
    if kp.get('_system') == '呼吸系统疾病':
        name = kp.get('name', '')
        system = kp.get('_system', '')
        chapter = kp.get('_chapter', '')
        node_id = f'textbook-{system}-{chapter}-{name}'.replace(' ', '-')
        
        if node_id not in miniapp_ids:
            missing.append(kp)
            print(f'- {name} (章节: {chapter})')

print(f'\n共遗漏 {len(missing)} 个知识点')

# 检查遗漏原因
print('\n=== 遗漏原因分析 ===')
for kp in missing:
    name = kp.get('name', '')
    structured = kp.get('structured', {})
    if not structured:
        print(f'{name}: 没有structured数据')
    elif structured.get('definition', '') == '教材中未详细展开':
        print(f'{name}: 定义未详细展开')

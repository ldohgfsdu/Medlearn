import json

# 读取structured.json
with open('g:/MedLearn/medlearn-extractor/output/structured.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

kps = data.get('knowledge_points', [])

# 统计
total = len(kps)
structured_count = sum(1 for kp in kps if kp.get('structurize_status') == 'success')
no_structure = sum(1 for kp in kps if kp.get('structurize_status') != 'success')

print('=== structured.json 统计 ===')
print(f'总知识点数: {total}')
print(f'已结构化: {structured_count}')
print(f'未结构化: {no_structure}')

# 按系统统计
systems = {}
for kp in kps:
    system = kp.get('_system', '未知')
    if system not in systems:
        systems[system] = {'total': 0, 'structured': 0}
    systems[system]['total'] += 1
    if kp.get('structurize_status') == 'success':
        systems[system]['structured'] += 1

print('\n=== 按系统统计 ===')
for system, stats in systems.items():
    print(f'{system}: {stats["structured"]}/{stats["total"]} 已结构化')

# 检查哪些知识点没有被导出到小程序
print('\n=== 未结构化的知识点 ===')
for kp in kps:
    if kp.get('structurize_status') != 'success':
        print(f'- {kp.get("name", "未知")} ({kp.get("_system", "未知")})')

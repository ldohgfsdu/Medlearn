import json

# 读取structured.json
with open('g:/MedLearn/medlearn-extractor/output/structured.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

kps = data.get('knowledge_points', [])

# 统计系统名称
systems = {}
for kp in kps:
    system = kp.get('_system', '未知')
    if system not in systems:
        systems[system] = 0
    systems[system] += 1

print('=== structured.json 中的系统名称 ===')
for system, count in systems.items():
    print(f'{system}: {count} 个知识点')

print('\n=== SYSTEM_MAP 中的系统名称 ===')
SYSTEM_MAP = {
    "呼吸系统疾病": ("respiratory", "pagesB"),
    "循环系统疾病": ("circulatory", "pagesA"),
    "消化系统疾病": ("digestive", "pagesB"),
    "泌尿系统疾病": ("urinary", "pagesC"),
    "血液系统疾病": ("hematologic", "pagesB"),
    "内分泌和代谢性疾病": ("endocrine", "pagesA"),
    "风湿性疾病": ("rheumatologic", "pagesC"),
    "理化因素所致疾病": ("toxicologic", "pagesC"),
}
for system in SYSTEM_MAP.keys():
    print(f'{system}')

print('\n=== 不匹配的系统 ===')
for system in systems.keys():
    if system not in SYSTEM_MAP:
        print(f'{system}: {systems[system]} 个知识点')

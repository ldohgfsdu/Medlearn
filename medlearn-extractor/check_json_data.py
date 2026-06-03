import json

# 读取一个JSON文件检查
with open('g:/MedLearn/mini-program/pagesB/data/respiratory.json', 'r', encoding='utf-8') as f:
    nodes = json.load(f)

if nodes:
    node = nodes[0]
    print('=== 第一个知识点 ===')
    print(f"标题: {node.get('title')}")
    print(f"\n=== dimensions字段 ===")
    dims = node.get('dimensions', {})
    if dims:
        for key, value in dims.items():
            if value and value != '教材中未详细展开':
                print(f"{key}: {value[:80]}...")
    else:
        print('没有dimensions字段')

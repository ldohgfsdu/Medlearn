"""更新extractedKnowledge.ts和extractedKnowledgeNodes.ts中的tags字段"""

import json
import re
from pathlib import Path

# 读取structured.json获取keywords
with open('g:/MedLearn/medlearn-extractor/output/structured.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

kps = data.get('knowledge_points', [])

# 创建name到keywords的映射
keywords_map = {}
for kp in kps:
    name = kp.get('name', '')
    structured = kp.get('structured', {})
    if structured:
        keywords = structured.get('keywords', [])
        aliases = structured.get('aliases', [])
        tags = []
        if keywords:
            tags.extend(keywords[:8])
        if aliases:
            tags.extend(aliases[:3])
        keywords_map[name] = tags

# 更新extractedKnowledgeNodes.ts
file_path = Path('g:/MedLearn/mini-program/src/data/extractedKnowledgeNodes.ts')
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JSON
match = re.search(r'export const extractedKnowledgeNodes: KnowledgeNode\[\] = (\[[\s\S]*?\]);', content)
if match:
    nodes = json.loads(match.group(1))
    
    # 更新tags
    for node in nodes:
        title = node.get('title', '')
        if title in keywords_map:
            node['tags'] = keywords_map[title]
    
    # 生成新的TypeScript文件
    output = f"""import type {{ KnowledgeNode }} from '../types/knowledge';

// 自动从教材 staging 生成（优化版 - 轻量级数据）
// 教材: 内科学 第10版
// bookId: internal-medicine-10-v7
// 生成时间: 2026-06-03
// 总知识点数: {len(nodes)}

export const extractedKnowledgeNodes: KnowledgeNode[] = {json.dumps(nodes, ensure_ascii=False, indent=2)};
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"✓ 更新extractedKnowledgeNodes.ts成功！")

# 更新extractedKnowledge.ts
file_path = Path('g:/MedLearn/mini-program/src/data/extractedKnowledge.ts')
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JSON
match = re.search(r'export const extractedKnowledgeNodes: KnowledgeNode\[\] = (\[[\s\S]*?\]);', content)
if match:
    nodes = json.loads(match.group(1))
    
    # 更新tags
    for node in nodes:
        title = node.get('title', '')
        if title in keywords_map:
            node['tags'] = keywords_map[title]
    
    # 生成新的TypeScript文件
    output = f"""import type {{ KnowledgeNode }} from '../types/knowledge';

// 自动从教材 staging 生成（优化版 - 轻量级数据）
// 教材: 内科学 第10版
// bookId: internal-medicine-10
// 生成时间: 2026-06-03
// 总知识点数: {len(nodes)}

export const extractedKnowledgeNodes: KnowledgeNode[] = {json.dumps(nodes, ensure_ascii=False, indent=2)};
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"✓ 更新extractedKnowledge.ts成功！")

print("\n示例tags:")
if keywords_map:
    for name, tags in list(keywords_map.items())[:3]:
        print(f"  {name}: {tags}")

"""优化extractedKnowledgeNodes.ts文件，只保留轻量级数据"""

import json
import re

# 读取文件
with open('g:/MedLearn/mini-program/src/data/extractedKnowledgeNodes.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# 提取JSON
match = re.search(r'export const extractedKnowledgeNodes: KnowledgeNode\[\] = (\[[\s\S]*?\]);', content)
if not match:
    print("无法解析文件")
    exit(1)

nodes = json.loads(match.group(1))

# 优化：只保留轻量级字段
optimized_nodes = []
for node in nodes:
    optimized_node = {
        "id": node["id"],
        "type": node["type"],
        "title": node["title"],
        "subject": node.get("subject", ""),
        "chapter": node.get("chapter", ""),
        "keyPoints": node.get("keyPoints", []),
        "tags": node.get("tags", []),
        "difficulty": node.get("difficulty", 2),
        "source": node.get("source", "seed"),
        "bookId": node.get("bookId", ""),
        "createdAt": node.get("createdAt", 0),
        "updatedAt": node.get("updatedAt", 0)
    }
    optimized_nodes.append(optimized_node)

# 生成新的TypeScript文件
output = f"""import type {{ KnowledgeNode }} from '../types/knowledge';

// 自动从教材 staging 生成（优化版 - 轻量级数据）
// 教材: 内科学 第10版
// bookId: internal-medicine-10-v7
// 生成时间: 2026-06-03
// 总知识点数: {len(optimized_nodes)}

export const extractedKnowledgeNodes: KnowledgeNode[] = {json.dumps(optimized_nodes, ensure_ascii=False, indent=2)};
"""

# 写入文件
with open('g:/MedLearn/mini-program/src/data/extractedKnowledgeNodes.ts', 'w', encoding='utf-8') as f:
    f.write(output)

print(f"✓ 优化完成！")
print(f"  - 原始节点数: {len(nodes)}")
print(f"  - 优化后节点数: {len(optimized_nodes)}")

# 检查文件大小
import os
size = os.path.getsize('g:/MedLearn/mini-program/src/data/extractedKnowledgeNodes.ts') / 1024
print(f"  - 优化后文件大小: {size:.2f} KB")

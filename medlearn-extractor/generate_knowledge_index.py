"""Generate knowledgeIndex.ts from seedKnowledgeNodes.ts"""

import json
import re
from pathlib import Path


def generate_knowledge_index():
    """从knowledgeNodes_for_miniapp.ts生成knowledgeIndex.ts"""
    
    # 读取knowledgeNodes_for_miniapp.ts
    seed_path = Path("g:/MedLearn/medlearn-extractor/output/knowledgeNodes_for_miniapp.ts")
    with open(seed_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 提取JSON数据
    # 找到export const seedKnowledgeNodes: KnowledgeNode[] = 后面的JSON
    match = re.search(r'export const seedKnowledgeNodes: KnowledgeNode\[\] = (\[[\s\S]*?\]);', content)
    if not match:
        print("无法解析seedKnowledgeNodes.ts")
        return
    
    json_str = match.group(1)
    
    # 解析JSON
    nodes = json.loads(json_str)
    
    # 生成knowledgeIndex数据
    index_nodes = []
    for node in nodes:
        index_node = {
            "id": node["id"],
            "type": node["type"],
            "title": node["title"],
            "subject": node.get("subject", ""),
            "chapter": node.get("chapter", ""),
            "tags": node.get("tags", []),
            "order": node.get("order", 0)
        }
        index_nodes.append(index_node)
    
    # 生成TypeScript文件
    output_path = Path("g:/MedLearn/mini-program/src/data/knowledgeIndex.ts")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('import type { KnowledgeNodeIndex } from "../types/knowledge";\n\n')
        f.write(f'// Lightweight index: {len(index_nodes)} entries, no full content\n\n')
        f.write('export const knowledgeIndex: KnowledgeNodeIndex[] = ')
        json.dump(index_nodes, f, ensure_ascii=False, indent=2)
        f.write(';\n')
    
    print(f"✓ 生成knowledgeIndex.ts成功！")
    print(f"  - 总知识点数: {len(index_nodes)}")
    print(f"  - 输出文件: {output_path}")
    
    # 显示示例
    if index_nodes:
        print("\n示例数据:")
        example = index_nodes[0]
        for key in ["id", "type", "title", "subject", "chapter"]:
            print(f"  {key}: {example[key]}")
        print(f"  tags: {example['tags'][:3]}...")


if __name__ == "__main__":
    generate_knowledge_index()

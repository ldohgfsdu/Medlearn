"""Export structured.json to mini-program format (KnowledgeNode)."""

import json
import time
from pathlib import Path

import config
from chapter_mapping import get_full_chapter_name


def format_content(structured: dict) -> str:
    """Format 9-dimension data to readable content string."""
    parts = []

    if structured.get("definition"):
        parts.append(f"📖 定义\n{structured['definition']}")

    if structured.get("etiology"):
        parts.append(f"\n🔬 病因\n{structured['etiology']}")

    if structured.get("pathogenesis"):
        parts.append(f"\n⚙️ 发病机制\n{structured['pathogenesis']}")

    if structured.get("pathology"):
        parts.append(f"\n🔬 病理\n{structured['pathology']}")

    if structured.get("manifestation"):
        parts.append(f"\n🩺 临床表现\n{structured['manifestation']}")

    if structured.get("examination"):
        parts.append(f"\n🔬 辅助检查\n{structured['examination']}")

    if structured.get("diagnosis"):
        parts.append(f"\n✅ 诊断\n{structured['diagnosis']}")

    if structured.get("treatment"):
        parts.append(f"\n💊 治疗\n{structured['treatment']}")

    if structured.get("prognosis"):
        parts.append(f"\n📊 预后\n{structured['prognosis']}")

    return "\n".join(parts)


def extract_key_points(structured: dict) -> list:
    """Extract key points from structured data."""
    key_points = []

    # Extract from definition
    if structured.get("definition"):
        key_points.append(f"定义：{structured['definition'][:100]}...")

    # Extract from manifestation
    if structured.get("manifestation"):
        lines = structured["manifestation"].split("\n")
        for line in lines[:3]:
            if line.strip() and len(line.strip()) > 10:
                key_points.append(line.strip()[:100])
                break

    # Extract from diagnosis
    if structured.get("diagnosis"):
        lines = structured["diagnosis"].split("\n")
        for line in lines[:2]:
            if line.strip() and len(line.strip()) > 10:
                key_points.append(line.strip()[:100])
                break

    # Extract from treatment
    if structured.get("treatment"):
        lines = structured["treatment"].split("\n")
        for line in lines[:2]:
            if line.strip() and len(line.strip()) > 10:
                key_points.append(line.strip()[:100])
                break

    # Ensure at least 2 key points
    if len(key_points) < 2:
        if structured.get("etiology"):
            key_points.append(f"病因：{structured['etiology'][:100]}...")
        if structured.get("prognosis"):
            key_points.append(f"预后：{structured['prognosis'][:100]}...")

    return key_points[:5]  # Max 5 key points


def export_for_miniapp():
    """Export structured data to mini-program format."""
    # Load structured data
    with open(config.STRUCTURED_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    kps = data.get("knowledge_points", [])

    # Convert to mini-program format
    miniapp_nodes = []

    # 按原始顺序添加序号
    for idx, kp in enumerate(kps):
        if kp.get("structurize_status") != "success":
            continue

        structured = kp.get("structured", {})
        if not structured:
            continue

        name = kp.get("name", "")
        system = kp.get("_system", "")
        chapter = kp.get("_chapter", "")
        
        # 获取完整的章节名称（带章节号）
        full_chapter = get_full_chapter_name(chapter)

        # Generate ID
        node_id = f"textbook-{system}-{chapter}-{name}".replace(" ", "-")

        # Format content
        content = format_content(structured)

        # Extract key points
        key_points = extract_key_points(structured)

        # Generate tags - 使用structured数据中的keywords
        tags = []
        
        # Add keywords from structured data
        keywords = structured.get("keywords", [])
        if keywords:
            tags.extend(keywords[:8])  # 最多8个关键词
        
        # Add aliases
        aliases = structured.get("aliases", [])
        if aliases:
            tags.extend(aliases[:3])  # 最多3个别名

        # Build node
        node = {
            "id": node_id,
            "type": "disease",
            "title": name,
            "subject": f"内科学 - {system}",
            "chapter": full_chapter,
            "knowledgePath": [system, full_chapter],
            "order": idx,
            "content": content,
            "keyPoints": key_points,
            "causalLinks": [],
            "relatedNodes": [],
            "difficulty": 2,
            "tags": tags,
            "source": "seed",
            "bookId": "internal-medicine-10",
            "textbook": "内科学",
            "edition": "第10版",
            "nodeSource": "segment-main",
            "inferred": False,
            "sourceSpan": {
                "pageStart": kp.get("start_page"),
                "pageEnd": None,
                "headingPath": [system, full_chapter, name]
            },
            "generatedAt": int(time.time() * 1000),
            "createdAt": int(time.time() * 1000),
            "updatedAt": int(time.time() * 1000)
        }

        miniapp_nodes.append(node)

    # Save to TypeScript format
    output_path = config.OUTPUT_DIR / "knowledgeNodes_for_miniapp.ts"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("import type { KnowledgeNode } from '../types/knowledge';\n\n")
        f.write(f"// Auto-generated from medlearn-extractor pipeline\n")
        f.write(f"// Total: {len(miniapp_nodes)} knowledge nodes\n")
        f.write(f"// Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("export const seedKnowledgeNodes: KnowledgeNode[] = ")
        json.dump(miniapp_nodes, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"✓ Exported {len(miniapp_nodes)} knowledge nodes to: {output_path}")

    # Show example
    if miniapp_nodes:
        print("\n示例数据结构:")
        example = miniapp_nodes[0]
        for key in ["id", "type", "title", "subject", "chapter"]:
            print(f"  {key}: {example[key]}")
        print(f"  content: {example['content'][:100]}...")
        print(f"  keyPoints: {example['keyPoints'][:2]}...")


if __name__ == "__main__":
    export_for_miniapp()

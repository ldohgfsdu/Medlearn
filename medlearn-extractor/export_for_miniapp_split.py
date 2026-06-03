"""Export structured.json to mini-program split format (by system)."""

import json
import time
from pathlib import Path

import config


def format_text_paragraphs(text: str) -> str:
    """Format text with proper line breaks for numbered items."""
    if not text:
        return ""
    
    import re
    
    # Split by numbered patterns like "1.", "2.", "（1）", "(1)", "①", "②"
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Add line break before numbered items
        if re.match(r'^[\d]+[\.\、]', line) or re.match(r'^[（\(][\d]+[）\)]', line) or re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩]', line):
            formatted_lines.append('')
            formatted_lines.append(line)
        # Add line break before bullet points
        elif line.startswith('•') or line.startswith('-') or line.startswith('·'):
            formatted_lines.append('')
            formatted_lines.append(line)
        # Add line break before specific markers
        elif any(line.startswith(marker) for marker in ['主要', '常见', '临床', '治疗', '诊断', '预防']):
            formatted_lines.append('')
            formatted_lines.append(line)
        else:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)


def format_content(structured: dict) -> str:
    """Format 9-dimension data to readable content string."""
    parts = []
    separator = "\n────────────────────────\n"

    if structured.get("definition"):
        formatted = format_text_paragraphs(structured['definition'])
        parts.append(f"📖 定义\n{formatted}")

    if structured.get("etiology"):
        formatted = format_text_paragraphs(structured['etiology'])
        parts.append(f"\n🔬 病因\n{formatted}")

    if structured.get("pathogenesis"):
        formatted = format_text_paragraphs(structured['pathogenesis'])
        parts.append(f"\n⚙️ 发病机制\n{formatted}")

    if structured.get("pathology"):
        formatted = format_text_paragraphs(structured['pathology'])
        parts.append(f"\n🔬 病理\n{formatted}")

    if structured.get("manifestation"):
        formatted = format_text_paragraphs(structured['manifestation'])
        parts.append(f"\n🩺 临床表现\n{formatted}")

    if structured.get("examination"):
        formatted = format_text_paragraphs(structured['examination'])
        parts.append(f"\n🔬 辅助检查\n{formatted}")

    if structured.get("diagnosis"):
        formatted = format_text_paragraphs(structured['diagnosis'])
        parts.append(f"\n✅ 诊断\n{formatted}")

    if structured.get("treatment"):
        formatted = format_text_paragraphs(structured['treatment'])
        parts.append(f"\n💊 治疗\n{formatted}")

    if structured.get("prognosis"):
        formatted = format_text_paragraphs(structured['prognosis'])
        parts.append(f"\n📊 预后\n{formatted}")

    # Add vindicate
    vindicate = structured.get("vindicate", {})
    if vindicate:
        has_content = False
        vindicate_parts = []
        vindicate_labels = {
            "vascular": "🩸 血管性",
            "infectious": "🦠 感染性",
            "neoplastic": "🔬 肿瘤性",
            "drug": "💊 药物性",
            "inflammatory": "🔥 炎症性",
            "congenital": "🧬 先天性",
            "autoimmune": "🛡️ 自身免疫性",
            "traumatic": "🩹 创伤性",
            "endocrine": "⚖️ 内分泌性"
        }
        for key, label in vindicate_labels.items():
            value = vindicate.get(key, "")
            if value and value != "教材中未详细展开" and value != "不适用" and len(value) > 5:
                has_content = True
                vindicate_parts.append(f"{label}：{value[:150]}")
        
        if has_content:
            parts.append("\n\n🔍 鉴别诊断（VINDICATE）")
            parts.extend(vindicate_parts)

    return separator.join(parts)


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


# System key mapping
SYSTEM_KEY_MAP = {
    "呼吸系统疾病": "respiratory",
    "循环系统疾病": "circulatory",
    "消化系统疾病": "digestive",
    "泌尿系统疾病": "urinary",
    "血液系统疾病": "hematologic",
    "内分泌和代谢性疾病": "endocrine",
    "风湿性疾病": "rheumatologic",
    "理化因素所致疾病": "toxicologic",
}

# Bucket mapping (which subpackage)
BUCKET_MAP = {
    "respiratory": "pagesB",
    "circulatory": "pagesA",
    "digestive": "pagesB",
    "urinary": "pagesC",
    "hematologic": "pagesB",
    "endocrine": "pagesA",
    "rheumatologic": "pagesC",
    "toxicologic": "pagesC",
}


def export_for_miniapp_split():
    """Export structured data to mini-program split format."""
    # Load structured data
    with open(config.STRUCTURED_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    kps = data.get("knowledge_points", [])

    # Group by system
    system_nodes = {}

    for kp in kps:
        if kp.get("structurize_status") != "success":
            continue

        structured = kp.get("structured", {})
        if not structured:
            continue

        name = kp.get("name", "")
        system = kp.get("_system", "")
        chapter = kp.get("_chapter", "")

        # Get system key
        system_key = SYSTEM_KEY_MAP.get(system, "other")

        # Generate ID
        node_id = f"textbook-{system}-{chapter}-{name}".replace(" ", "-")

        # Format content
        content = format_content(structured)

        # Extract key points
        key_points = extract_key_points(structured)

        # Generate tags
        tags = [
            system,
            chapter,
            name,
            "internal-medicine-10",
            "内科学",
            "第10版"
        ]

        # Add aliases to tags
        aliases = structured.get("aliases", [])
        if aliases:
            tags.extend(aliases[:3])

        # Add keywords to tags
        keywords = structured.get("keywords", [])
        if keywords:
            tags.extend(keywords[:5])

        # Build node
        node = {
            "id": node_id,
            "type": "disease",
            "title": name,
            "subject": f"内科学 - {system}",
            "chapter": chapter,
            "knowledgePath": [system, chapter],
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
                "headingPath": [system, chapter, name]
            },
            "dimensions": {
                "definition": structured.get("definition", ""),
                "etiology": structured.get("etiology", ""),
                "pathogenesis": structured.get("pathogenesis", ""),
                "pathology": structured.get("pathology", ""),
                "manifestation": structured.get("manifestation", ""),
                "examination": structured.get("examination", ""),
                "diagnosis": structured.get("diagnosis", ""),
                "treatment": structured.get("treatment", ""),
                "prognosis": structured.get("prognosis", ""),
                "vindicate": structured.get("vindicate", {})
            },
            "generatedAt": int(time.time() * 1000),
            "createdAt": int(time.time() * 1000),
            "updatedAt": int(time.time() * 1000)
        }

        if system_key not in system_nodes:
            system_nodes[system_key] = []
        system_nodes[system_key].append(node)

    # Save each system to its bucket
    mini_program_src = Path("g:/MedLearn/mini-program/src")

    for system_key, nodes in system_nodes.items():
        bucket = BUCKET_MAP.get(system_key, "pagesB")
        data_dir = mini_program_src / bucket / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        output_path = data_dir / f"{system_key}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(nodes, f, ensure_ascii=False, indent=2)

        print(f"✓ {system_key}: {len(nodes)} nodes → {output_path}")

    # Also update knowledgeIndex.ts
    index_path = mini_program_src / "data" / "knowledgeIndex.ts"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write('import type { KnowledgeNodeIndex } from "../types/knowledge";\n\n')
        f.write(f"// Auto-generated from medlearn-extractor pipeline\n")
        f.write(f"// Total: {sum(len(nodes) for nodes in system_nodes.values())} knowledge nodes\n")
        f.write(f"// Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("export const knowledgeIndex: KnowledgeNodeIndex[] = [\n")

        order = 0
        for system_key, nodes in system_nodes.items():
            for node in nodes:
                f.write("  {\n")
                f.write(f'    "id": "{node["id"]}",\n')
                f.write(f'    "type": "{node["type"]}",\n')
                f.write(f'    "title": "{node["title"]}",\n')
                f.write(f'    "subject": "{node["subject"]}",\n')
                f.write(f'    "chapter": "{node["chapter"]}",\n')
                f.write(f'    "tags": {json.dumps(node["tags"], ensure_ascii=False)},\n')
                f.write(f'    "order": {order}\n')
                f.write("  },\n")
                order += 1

        f.write("];\n")

    print(f"\n✓ Updated knowledgeIndex.ts")

    total = sum(len(nodes) for nodes in system_nodes.values())
    print(f"\n总计: {total} 个知识点")


if __name__ == "__main__":
    export_for_miniapp_split()

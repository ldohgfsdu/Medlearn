"""生成小程序用的JSON数据文件，使用9维结构化内容"""

import json
from pathlib import Path
from chapter_mapping import get_full_chapter_name

# 系统映射
SYSTEM_MAP = {
    "呼吸系统疾病": ("respiratory", "pagesB"),
    "循环系统疾病": ("circulatory", "pagesA"),
    "消化系统疾病": ("digestive", "pagesB"),
    "泌尿系统疾病": ("urinary", "pagesC"),
    "血液系统疾病": ("hematologic", "pagesB"),
    "内分泌和代谢性疾病": ("endocrine", "pagesA"),
    "风湿性疾病": ("rheumatologic", "pagesC"),
    "风湿免疫病": ("rheumatologic", "pagesC"),  # 别名
    "理化因素所致疾病": ("toxicologic", "pagesC"),
}


def format_content_from_dimensions(structured: dict) -> str:
    """将9维结构化数据格式化为可读内容"""
    parts = []
    
    dimensions = [
        ("definition", "📖 定义"),
        ("etiology", "🔬 病因"),
        ("pathogenesis", "⚙️ 发病机制"),
        ("pathology", "🔬 病理"),
        ("manifestation", "🩺 临床表现"),
        ("examination", "📊 辅助检查"),
        ("diagnosis", "✅ 诊断标准"),
        ("treatment", "💊 治疗"),
        ("prognosis", "📈 预后"),
    ]
    
    for key, label in dimensions:
        value = structured.get(key, "")
        if value and value != "教材中未详细展开" and value != "不适用":
            parts.append(f"{label}\n{value}")
    
    return "\n\n".join(parts)


def generate_json_data():
    """生成JSON数据文件"""
    # 读取structured.json
    with open("g:/MedLearn/medlearn-extractor/output/structured.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    kps = data.get("knowledge_points", [])
    
    # 按系统分组
    system_nodes = {}
    
    for idx, kp in enumerate(kps):
        if kp.get("structurize_status") != "success":
            continue
        
        structured = kp.get("structured", {})
        if not structured:
            continue
        
        name = kp.get("name", "")
        system = kp.get("_system", "")
        chapter = kp.get("_chapter", "")
        
        # 获取系统信息
        if system not in SYSTEM_MAP:
            continue
        
        sys_key, bucket = SYSTEM_MAP[system]
        
        # 获取完整章节名称
        full_chapter = get_full_chapter_name(chapter)
        
        # 生成ID
        node_id = f"textbook-{system}-{chapter}-{name}".replace(" ", "-")
        
        # 格式化内容
        content = format_content_from_dimensions(structured)
        
        # 提取精炼的keyPoints
        key_points = []
        
        # 判断是否为疾病类知识点
        is_disease = kp.get("type") == "disease" or "疾病" in name or "症" in name or "炎" in name
        # 判断是否为概述类知识点
        is_overview = "概述" in name or "总论" in name
        
        import re
        
        # 1. 定义（精简版）- 所有类型都显示
        if structured.get("definition"):
            defn = structured["definition"]
            # 提取第一句话作为定义要点
            first_sentence = defn.split("。")[0] if "。" in defn else defn[:80]
            # 对于概述类，只显示定义，不显示疾病分类列表
            if is_overview:
                key_points.append(f"定义：{first_sentence}")
            else:
                key_points.append(f"定义：{first_sentence}")
        
        # 2. 临床表现（只提取类型名称）- 仅疾病类显示，概述类不显示
        if is_disease and not is_overview and structured.get("manifestation"):
            manifest = structured["manifestation"]
            # 提取临床类型名称
            # 匹配"1. xxx：2. xxx：3. xxx："或"1. xxx 2. xxx 3. xxx"模式
            type_matches = re.findall(r'\d+\.\s*([^：:。]+?)(?:[：:。]|$)', manifest)
            if type_matches:
                types = [t.strip() for t in type_matches[:5] if t.strip()]
                if types:
                    key_points.append(f"临床类型：{'、'.join(types)}")
        
        # 3. 核心机制/特点 - 非疾病类显示，从pathogenesis或pathology提取
        if not is_disease and not is_overview:
            if structured.get("pathogenesis") and structured["pathogenesis"] != "教材中未详细展开":
                pgs = structured["pathogenesis"]
                first_sentence = pgs.split("。")[0] if "。" in pgs else pgs[:80]
                key_points.append(f"核心机制：{first_sentence}")
            elif structured.get("pathology") and structured["pathology"] != "教材中未详细展开":
                path = structured["pathology"]
                first_sentence = path.split("。")[0] if "。" in path else path[:80]
                key_points.append(f"核心特点：{first_sentence}")
        
        # 4. 病因（精简版）- 仅疾病类显示，概述类不显示
        if is_disease and not is_overview and structured.get("etiology"):
            etio = structured["etiology"]
            if etio != "教材中未详细展开":
                first_sentence = etio.split("。")[0] if "。" in etio else etio[:80]
                key_points.append(f"病因：{first_sentence}")
        
        # 5. 治疗原则（精简版）- 仅疾病类显示，概述类不显示
        if is_disease and not is_overview and structured.get("treatment"):
            treat = structured["treatment"]
            if treat != "教材中未详细展开":
                first_sentence = treat.split("。")[0] if "。" in treat else treat[:80]
                key_points.append(f"治疗：{first_sentence}")
        
        # 6. 诊断（精简版）- 仅疾病类显示，概述类不显示
        if is_disease and not is_overview and structured.get("diagnosis"):
            diag = structured["diagnosis"]
            if diag != "教材中未详细展开":
                first_sentence = diag.split("。")[0] if "。" in diag else diag[:80]
                key_points.append(f"诊断：{first_sentence}")
        
        # 生成tags（使用keywords）
        tags = []
        keywords = structured.get("keywords", [])
        if keywords:
            tags.extend(keywords[:8])
        aliases = structured.get("aliases", [])
        if aliases:
            tags.extend(aliases[:3])
        
        # 构建节点
        node = {
            "id": node_id,
            "type": "disease",
            "title": name,
            "subject": f"内科学 - {system}",
            "chapter": full_chapter,
            "knowledgePath": [system, full_chapter],
            "order": idx,
            "content": content,
            "keyPoints": key_points[:5],
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
            "generatedAt": 1780452785000,
            "createdAt": 1780452785000,
            "updatedAt": 1780452785000,
            # 保存原始9维数据，供详情页使用
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
            }
        }
        
        # 按系统分组
        if sys_key not in system_nodes:
            system_nodes[sys_key] = []
        system_nodes[sys_key].append(node)
    
    # 生成JSON文件
    output_dir = Path("g:/MedLearn/mini-program")
    
    for sys_key, nodes in system_nodes.items():
        # 确定输出目录
        bucket = SYSTEM_MAP[[k for k, v in SYSTEM_MAP.items() if v[0] == sys_key][0]][1]
        output_path = output_dir / f"{bucket}/data/{sys_key}.json"
        
        # 创建目录
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(nodes, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 生成 {output_path}: {len(nodes)} 个知识点")
    
    print(f"\n✓ 总共生成 {sum(len(v) for v in system_nodes.values())} 个知识点")


if __name__ == "__main__":
    generate_json_data()

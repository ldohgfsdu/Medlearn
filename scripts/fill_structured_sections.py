"""
轻量脚本：为已有 knowledge_nodes 提取 structured_sections 并更新到数据库。
不需要重新跑完整入库流程，也不需要 PDF 或向量化。

用法：
  python scripts/fill_structured_sections.py
  python scripts/fill_structured_sections.py --dry-run   # 只看效果不写入
"""

import os
import sys
import io
import json
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ .env 中缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── 结构化标题 ──────────────────────────────────────────────────────

DISEASE_STRUCTURE_TITLES = [
    "定义", "概述", "流行病学", "病因", "发病机制", "病因与发病机制",
    "病理", "病理生理", "临床表现", "症状", "体征",
    "检查", "辅助检查", "实验室检查", "影像学检查",
    "诊断", "鉴别诊断", "诊断标准",
    "治疗", "治疗原则", "药物治疗", "手术治疗",
    "预后", "预防", "并发症", "分类", "分型",
]

# 长标题优先匹配
DISEASE_STRUCTURE_TITLES.sort(key=len, reverse=True)


def extract_structured_sections(text: str) -> list[dict]:
    """从疾病文本中提取结构化子节点
    
    支持的格式：
    - 【发病机制】xxx
    - 发病机制：xxx
    - 一、发病机制
    - (一)发病机制
    - 1.发病机制
    """
    if not text or len(text) < 50:
        return []

    # 先把连续文本按标题标记拆分成行
    # 处理 【标题】 格式：在 【 前插入换行
    text = re.sub(r'([。！？；\n])\s*【', r'\1\n【', text)
    # 处理 "一、病因" 格式
    text = re.sub(r'([。！？；\n])\s*([一二三四五六七八九十]+[、.．])', r'\1\n\2', text)
    # 处理 "(一)病因" 格式
    text = re.sub(r'([。！？；\n])\s*([（(][一二三四五六七八九十\d]+[）)])', r'\1\n\2', text)
    # 处理 "1." 数字标题格式（但不要误拆小数如 1.5）
    text = re.sub(r'([。！？；\n])\s*(\d+[、.．]\s*[^\d])', r'\1\n\2', text)

    lines = text.split("\n")
    sections = []
    current_section = None
    current_content = []

    for line in lines:
        s = line.strip()
        if not s:
            continue

        matched_title = None
        matched_rest = ""

        for title in DISEASE_STRUCTURE_TITLES:
            esc = re.escape(title)
            patterns = [
                # 【标题】 格式（最常见于教材）
                (rf'^【{esc}】\s*(.*)', True),
                # 【标题】：内容
                (rf'^【{esc}】\s*[：:]\s*(.*)', True),
                # 标题： 单独一行
                (rf'^{esc}\s*[：:]\s*$', False),
                # 标题：内容
                (rf'^{esc}\s*[：:]\s*(.+)', True),
                # 一、标题
                (rf'^[一二三四五六七八九十\d]+[、.．]\s*{esc}\s*[：:]*\s*(.*)', True),
                # (一)标题
                (rf'^[（(][一二三四五六七八九十\d]+[）)]\s*{esc}\s*[：:]*\s*(.*)', True),
                # 1.标题
                (rf'^\d+\.\s*{esc}\s*[：:]*\s*(.*)', True),
            ]
            for pattern, has_rest in patterns:
                m = re.match(pattern, s)
                if m:
                    matched_title = title
                    if has_rest and m.group(1).strip():
                        matched_rest = m.group(1).strip()
                    break
            if matched_title:
                break

        if matched_title:
            if current_section and current_content:
                sections.append({
                    "title": current_section,
                    "content": "\n".join(current_content).strip()
                })
            current_section = matched_title
            current_content = [matched_rest] if matched_rest else []
        else:
            if current_section:
                current_content.append(s)

    if current_section and current_content:
        sections.append({
            "title": current_section,
            "content": "\n".join(current_content).strip()
        })

    return sections


def main():
    dry_run = "--dry-run" in sys.argv

    print(f"\n{'='*60}")
    print(f"📋 填充 structured_sections {'(DRY RUN)' if dry_run else ''}")
    print(f"{'='*60}")

    # 1. 获取所有有 content 但没有 structured_sections 的节点
    print("\n📥 查询数据库...")
    all_nodes = []
    offset = 0
    while True:
        res = supabase.table("knowledge_nodes")\
            .select("id, title, type, content, structured_sections, subject, chapter, sub_chapter, level")\
            .range(offset, offset + 999)\
            .execute()
        if not res.data:
            break
        all_nodes.extend(res.data)
        if len(res.data) < 1000:
            break
        offset += 1000

    print(f"   总节点数: {len(all_nodes)}")

    # 2. 筛选需要处理的节点
    needs_structuring = []
    for node in all_nodes:
        content = node.get("content") or ""
        ss = node.get("structured_sections")
        # 没有 structured_sections 或为空，且有足够内容
        if content and len(content) >= 100 and (not ss or (isinstance(ss, list) and len(ss) == 0)):
            needs_structuring.append(node)

    print(f"   需要提取结构化的节点: {len(needs_structuring)}")

    if not needs_structuring:
        print("✅ 所有节点都已有结构化数据，无需处理")
        return

    # 3. 提取结构化子节点
    print("\n🔍 提取结构化子节点...")
    updates = []
    no_sections = 0

    for node in needs_structuring:
        sections = extract_structured_sections(node["content"])
        if sections and len(sections) >= 2:
            updates.append({
                "id": node["id"],
                "structured_sections": sections,
            })
            if len(updates) <= 5:
                titles = [s["title"] for s in sections]
                print(f"   ✅ [{node['title']}] → {titles}")
        else:
            no_sections += 1

    print(f"\n   提取成功: {len(updates)} 个节点")
    print(f"   无法提取: {no_sections} 个节点（内容格式不匹配）")

    if not updates:
        print("⚠️  没有可更新的节点")
        return

    # 4. 同时修复缺少 sub_chapter / level 的节点
    print("\n🔧 修复 sub_chapter / level 字段...")
    field_updates = []
    for node in all_nodes:
        update_fields = {}
        # 修复 subject：如果是篇名而非教材名
        subject = node.get("subject") or ""
        chapter = node.get("chapter") or ""
        if subject and re.match(r'^第[一二三四五六七八九十百千]+[篇部分]', subject):
            # subject 是篇名，需要改成教材名
            # 从 chapter 推断（如果 chapter 不是篇名）
            update_fields["subject"] = chapter if chapter and not re.match(r'^第[一二三四五六七八九十百千]+[篇部分]', chapter) else subject

        # 修复 sub_chapter：如果没有，从 title 推断
        if not node.get("sub_chapter") and node.get("level") == 3:
            update_fields["sub_chapter"] = node.get("title", "")

        if update_fields:
            update_fields["id"] = node["id"]
            field_updates.append(update_fields)

    print(f"   需要修复字段的节点: {len(field_updates)}")

    if dry_run:
        print(f"\n🧪 DRY RUN - 不写入数据库")
        print(f"   将更新 {len(updates)} 个节点的 structured_sections")
        print(f"   将修复 {len(field_updates)} 个节点的 sub_chapter/level")
        return

    # 5. 写入数据库（批量 PATCH，只更新 structured_sections）
    print("\n💾 写入数据库...")

    BATCH = 20
    ss_success = 0
    ss_fail = 0

    for i in range(0, len(updates), BATCH):
        batch = updates[i:i+BATCH]
        for item in batch:
            try:
                supabase.table("knowledge_nodes")\
                    .update({"structured_sections": item["structured_sections"]})\
                    .eq("id", item["id"])\
                    .execute()
                ss_success += 1
            except Exception as e:
                ss_fail += 1
                if ss_fail <= 3:
                    print(f"   ❌ 更新失败 [{item['id']}]: {e}")
        print(f"   📊 进度: {ss_success}/{len(updates)}")

    print(f"   structured_sections: 成功 {ss_success}, 失败 {ss_fail}")

    # 批量写入字段修复
    ff_success = 0
    ff_fail = 0

    for i in range(0, len(field_updates), BATCH):
        batch = field_updates[i:i+BATCH]
        for item in batch:
            try:
                update_data = {k: v for k, v in item.items() if k != "id"}
                supabase.table("knowledge_nodes")\
                    .update(update_data)\
                    .eq("id", item["id"])\
                    .execute()
                ff_success += 1
            except Exception as e:
                ff_fail += 1
                if ff_fail <= 3:
                    print(f"   ❌ 修复失败 [{item['id']}]: {e}")

    print(f"   字段修复: 成功 {ff_success}, 失败 {ff_fail}")

    print(f"\n{'='*60}")
    print(f"🎉 完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

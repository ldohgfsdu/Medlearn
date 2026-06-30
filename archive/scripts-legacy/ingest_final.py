"""
DEPRECATED — use scripts/ingest_knowledge.py (V3 manifest production path).
See docs/PIPELINE_INDEX.md.

Medlearn 教材入库脚本（合并最终版）
合并自：ingest_with_tree.py + extract_knowledge.py
功能：知识树同步 + 句子感知分块 + 断点续传 + GPU 加速 + 并发写库
      + content 填充 + key_points AI 提取 + causal_links AI 生成

环境变量：
  SUPABASE_URL            - Supabase 项目 URL（必填）
  SUPABASE_SERVICE_ROLE_KEY - Supabase Service Role Key（必填）
  MODEL_PATH              - 向量模型路径（默认 BAAI/bge-m3）
  AI_API_KEY              - OpenAI 兼容 API Key（用于 key_points/causal_links 提取，可选）
  AI_API_BASE_URL         - OpenAI 兼容 API Base URL（可选，默认 https://api.openai.com/v1）
  AI_MODEL                - AI 模型名称（可选，默认 gpt-4o-mini）

用法：
  python ingest_final.py <PDF路径>           # 正常处理（支持断点续传）
  python ingest_final.py <PDF路径> --reset   # 清空后重新处理
  python ingest_final.py <PDF路径> --skip-ai # 跳过 AI 提取步骤（key_points + causal_links）
"""

import os
import sys
import re
import io
import json
import hashlib
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pymupdf as fitz
import requests as http_requests
from dotenv import load_dotenv
from supabase import create_client

# Windows 终端 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── 配置 ──────────────────────────────────────────────────────────────

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
MODEL_PATH   = os.getenv("MODEL_PATH", "BAAI/bge-large-zh-v1.5")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")

# AI API 配置（用于 key_points / causal_links 提取）
AI_API_KEY      = os.getenv("AI_API_KEY", "")
AI_API_BASE_URL = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1")
AI_MODEL        = os.getenv("AI_MODEL", "gpt-4o-mini")

# SiliconFlow Embedding API 配置（用于向量化）
SILICONFLOW_KEY  = os.getenv("SILICONFLOW_KEY", "")
EMBED_MODEL      = os.getenv("EMBED_MODEL", "BAAI/bge-large-zh-v1.5")
EMBED_DIM        = 1024  # bge-large-zh-v1.5 输出维度

# 向量化 API 参数
EMBED_API_BATCH  = 20    # SiliconFlow 单次 embedding 请求数量
DB_BATCH         = 100   # Supabase 单次写入条数

# 分块参数（bge-m3 max_seq_len=8192，中文约 1 字=1 token，留余量）
CHUNK_SIZE    = 450
CHUNK_OVERLAP = 80
MIN_CHUNK_LEN = 30

# AI 调用重试配置
AI_MAX_RETRIES = 3
AI_RETRY_DELAY = 2  # 秒

# ── 启动检查 ──────────────────────────────────────────────────────────

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ .env 中缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

# 检查向量化方式：优先使用 API，其次使用本地模型
USE_LOCAL_MODEL = not SILICONFLOW_KEY and os.getenv("USE_LOCAL_MODEL", "true").lower() == "true"

if SILICONFLOW_KEY:
    print(f"📦 向量模型: {EMBED_MODEL} (SiliconFlow API)  维度={EMBED_DIM}")
elif USE_LOCAL_MODEL:
    print(f"📦 向量模型: {MODEL_PATH} (本地模型)")
else:
    print("❌ .env 中缺少 SILICONFLOW_KEY，且未设置 USE_LOCAL_MODEL=true")
    print("   请配置以下任一方式：")
    print("   1. 设置 SILICONFLOW_KEY=你的API密钥")
    print("   2. 设置 USE_LOCAL_MODEL=true 使用本地模型")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── AI 调用工具函数 ──────────────────────────────────────────────────

def call_ai_api(prompt: str, max_retries: int = AI_MAX_RETRIES) -> str | None:
    """调用 OpenAI 兼容 API，带重试。失败返回 None。"""
    if not AI_API_KEY:
        print("⚠️  AI_API_KEY 未配置，跳过 AI 调用")
        return None

    url = f"{AI_API_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": AI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 2000,
    }

    for attempt in range(1, max_retries + 1):
        try:
            resp = http_requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"   ⚠️  AI 调用失败（第 {attempt}/{max_retries} 次）: {e}")
            if attempt < max_retries:
                time.sleep(AI_RETRY_DELAY * attempt)
    return None


def parse_json_response(text: str) -> list | dict | None:
    """从 AI 返回文本中解析 JSON，兼容 markdown 代码块包裹。"""
    if not text:
        return None
    # 去掉 markdown 代码块包裹
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取 JSON 数组或对象
        match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        print(f"   ⚠️  JSON 解析失败，原始文本: {text[:200]}")
        return None


def extract_key_points(title: str, content: str) -> list[str]:
    """用 AI 从知识点内容中提取 3-5 个关键要点。"""
    # 截断过长内容避免 token 超限
    truncated = content[:3000] if len(content) > 3000 else content
    prompt = (
        f"从以下医学知识点内容中提取3-5个关键要点，每个要点一句话，"
        f"返回JSON数组格式如[\"要点1\",\"要点2\"]\n\n"
        f"知识点标题：{title}\n\n"
        f"内容：\n{truncated}"
    )
    result = call_ai_api(prompt)
    if result is None:
        return []
    parsed = parse_json_response(result)
    if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
        return parsed
    return []


def generate_causal_links(nodes: list[dict]) -> list[dict]:
    """
    对同一 chapter 下的知识点，用 AI 分析它们之间的因果/推导关系。
    每批处理 5-10 个节点。
    返回格式: [{"from": "标题", "to": "标题", "relation": "关系描述"}, ...]
    """
    if len(nodes) < 2:
        return []

    titles_text = "\n".join(f"{i+1}. {n['title']}" for i, n in enumerate(nodes))
    prompt = (
        f"分析以下医学知识点之间的因果/推导关系，"
        f"返回JSON数组，每个元素格式为 {{\"from\": \"知识点标题\", \"to\": \"知识点标题\", \"relation\": \"关系描述\"}}\n"
        f"只返回确实存在因果或推导关系的配对，不要强行关联。\n\n"
        f"知识点列表：\n{titles_text}"
    )
    result = call_ai_api(prompt)
    if result is None:
        return []
    parsed = parse_json_response(result)
    if isinstance(parsed, list):
        valid = []
        for item in parsed:
            if isinstance(item, dict) and "from" in item and "to" in item and "relation" in item:
                valid.append(item)
        return valid
    return []


# ── 工具函数 ──────────────────────────────────────────────────────────

def classify_node_type(title: str) -> str:
    """根据标题关键词判断知识点类别"""
    checks = [
        ("disease",   ["病", "症", "炎", "癌", "瘤", "综合征", "障碍", "中毒", "损伤", "衰竭", "梗死", "栓塞"]),
        ("symptom",   ["痛", "热", "咳", "喘", "肿", "出血", "痉挛", "麻痹"]),
        ("exam",      ["检查", "检验", "影像", "超声", "CT", "MRI", "X线", "心电图"]),
        ("treatment", ["治疗", "手术", "药物", "用药", "化疗", "放疗", "介入"]),
    ]
    for node_type, keywords in checks:
        if any(kw in title for kw in keywords):
            return node_type
    return "concept"


def sentence_aware_chunk(text: str) -> list[str]:
    """
    句子感知分块：按中文句子边界切割，不在句子中间截断。
    比滑动窗口更适合语义检索。
    """
    sentences = re.split(r'(?<=[。！？；\n])', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks, current = [], ""
    for sent in sentences:
        if len(current) + len(sent) <= CHUNK_SIZE:
            current += sent
        else:
            if len(current) >= MIN_CHUNK_LEN:
                chunks.append(current)
            # overlap：取上一块末尾作为上下文
            tail = chunks[-1][-CHUNK_OVERLAP:] if chunks else ""
            current = tail + sent

    if len(current) >= MIN_CHUNK_LEN:
        chunks.append(current)

    return chunks


def build_page_to_node(toc: list[dict], knowledge_nodes: list[dict]) -> dict[int, str]:
    """
    预建 page_number → node_id 映射，O(1) 查找。
    策略：每页对应最近的（页码 ≤ 当前页）TOC 节点。
    """
    if not toc or not knowledge_nodes:
        return {}

    node_id_by_title = {n["title"]: n["id"] for n in knowledge_nodes}
    sorted_entries = sorted(
        [(e["page"], e["title"]) for e in toc if e["title"] in node_id_by_title],
        key=lambda x: x[0]
    )
    if not sorted_entries:
        return {}

    page_map: dict[int, str] = {}
    ei = 0
    max_page = sorted_entries[-1][0] + 300

    for page in range(1, max_page):
        while ei + 1 < len(sorted_entries) and sorted_entries[ei + 1][0] <= page:
            ei += 1
        if sorted_entries[ei][0] <= page:
            page_map[page] = node_id_by_title[sorted_entries[ei][1]]

    return page_map


def fetch_existing_chunk_indices(document_name: str) -> set[int]:
    """查询已有 chunk 的 chunk_index，用于断点续传"""
    indices = set()
    offset = 0
    while True:
        res = supabase.table("document_chunks")\
            .select("chunk_index")\
            .eq("document_name", document_name)\
            .range(offset, offset + 999)\
            .execute()
        if not res.data:
            break
        indices.update(row["chunk_index"] for row in res.data)
        if len(res.data) < 1000:
            break
        offset += 1000
    return indices


def write_batch_to_db(batch: list[dict], batch_idx: int) -> int:
    """写一批 chunk 到 Supabase，返回写入数量（含重试）"""
    for attempt in range(3):
        try:
            supabase.table("document_chunks").insert(batch).execute()
            return len(batch)
        except Exception as e:
            if attempt == 2:
                raise
            wait = 2 ** attempt
            print(f"  ⚠️ DB 写入失败 (batch {batch_idx}, 重试 {attempt+1}/3): {e}, {wait}s 后重试...")
            time.sleep(wait)
    return 0


def get_embeddings_api(texts: list[str]) -> list[list[float]]:
    """调用 SiliconFlow Embedding API 批量获取向量（含重试）"""
    for attempt in range(3):
        try:
            resp = http_requests.post(
                "https://api.siliconflow.cn/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {SILICONFLOW_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": EMBED_MODEL,
                    "input": texts,
                },
                timeout=60,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Embedding API 失败: {resp.status_code} {resp.text[:200]}")
            result = resp.json()
            # 按 index 排序确保顺序一致
            sorted_data = sorted(result["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in sorted_data]
        except Exception as e:
            if attempt == 2:
                raise
            wait = 2 ** attempt
            print(f"  ⚠️ Embedding API 失败 (重试 {attempt+1}/3): {e}, {wait}s 后重试...")
            time.sleep(wait)
    return []


# ── 本地模型支持 ──────────────────────────────────────────────────────

_local_model = None

def get_local_model():
    """获取本地模型（懒加载）"""
    global _local_model
    if _local_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print(f"📦 正在加载本地模型: {MODEL_PATH}...")
            _local_model = SentenceTransformer(MODEL_PATH)
            dimension = _local_model.get_sentence_embedding_dimension()
            if dimension != EMBED_DIM:
                raise RuntimeError(
                    f"Local embedding dimension mismatch: expected {EMBED_DIM}, got {dimension}"
                )
            print(f"✅ 本地模型加载成功，维度: {_local_model.get_sentence_embedding_dimension()}")
        except ImportError:
            print("❌ 未安装 sentence-transformers，请运行: pip install sentence-transformers")
            raise
        except Exception as e:
            print(f"❌ 本地模型加载失败: {e}")
            raise
    return _local_model


def get_embeddings_local(texts: list[str]) -> list[list[float]]:
    """使用本地模型批量获取向量"""
    try:
        response = http_requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": OLLAMA_EMBED_MODEL, "input": texts},
            timeout=300,
        )
        response.raise_for_status()
        embeddings = response.json().get("embeddings", [])
        if len(embeddings) != len(texts):
            raise RuntimeError(
                f"Local embedding count mismatch: expected {len(texts)}, got {len(embeddings)}"
            )
        if any(len(vector) != EMBED_DIM for vector in embeddings):
            dimensions = sorted({len(vector) for vector in embeddings})
            raise RuntimeError(
                f"Local embedding dimension mismatch: expected {EMBED_DIM}, got {dimensions}"
            )
        return embeddings
    except Exception as e:
        raise RuntimeError("Local embedding generation failed") from e
        print(f"⚠️  本地模型加载失败，使用随机向量进行测试: {e}")
        # 使用随机向量进行测试（仅用于验证知识点提取优化效果）
        import random
        random.seed(42)  # 固定随机种子，保证可重复性
        dim = 768  # 默认维度
        return [[random.random() for _ in range(dim)] for _ in texts]


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """根据配置选择向量化方式"""
    if SILICONFLOW_KEY:
        return get_embeddings_api(texts)
    else:
        return get_embeddings_local(texts)


# ── 主流程 ────────────────────────────────────────────────────────────

def process_textbook(pdf_path: str, reset: bool = False, skip_ai: bool = False):
    if not os.path.exists(pdf_path):
        print(f"❌ 找不到文件: {pdf_path}")
        return

    doc           = fitz.open(pdf_path)
    textbook_name = Path(pdf_path).stem
    total_pages   = doc.page_count

    print(f"\n{'='*60}")
    print(f"📖 教材: {textbook_name}  ({total_pages} 页)")
    print(f"{'='*60}")

    # ── Step 0: 清空旧数据（--reset 模式）──────────────────────────
    if reset:
        print("🗑  清空旧数据...")
        supabase.table("knowledge_nodes").delete().eq("textbook", textbook_name).execute()
        supabase.table("document_chunks").delete().eq("document_name", textbook_name).execute()
        print("✅ 清空完成")

    # ── Step 1: 同步知识树 ────────────────────────────────────────
    print("\nStep 1: 扫描目录，同步知识树...")
    raw_toc = doc.get_toc()
    toc = [
        {"level": lvl, "title": title.replace('\n', '').strip(), "page": page}
        for lvl, title, page in raw_toc
        if lvl <= 3 and title.strip()
    ]

    knowledge_nodes = []
    current_part = current_chapter = ""

    for i, entry in enumerate(toc):
        lvl, title, page = entry["level"], entry["title"], entry["page"]
        if lvl == 1:
            current_part    = title
            current_chapter = ""
        elif lvl == 2:
            current_chapter = title

        if lvl >= 2:
            node_id = hashlib.md5(f"{textbook_name}_{title}_{page}".encode()).hexdigest()[:12]

            # 构建 knowledge_path：[part, chapter, title]
            path_parts = []
            if current_part:
                path_parts.append(current_part)
            if lvl == 3 and current_chapter:
                path_parts.append(current_chapter)
            path_parts.append(title)
            knowledge_path = path_parts

            knowledge_nodes.append({
                "id":             node_id,
                "title":          title,
                "subject":        textbook_name,
                "chapter":        current_part or "其他",
                "knowledge_path": knowledge_path,
                "content":        None,
                "key_points":     None,
                "causal_links":   None,
                "related_nodes":  None,
                "type":           classify_node_type(title),
                "textbook":       textbook_name,
                "source":         "textbook_auto",
                "order_num":      i,
                # 注意: PostgREST 不会忽略未知列，如果 sub_chapter/level 列不存在 upsert 会失败
                # 确保已运行 001_initial_schema.sql 或 006_extract_overhaul.sql 添加这些列
                "sub_chapter":    current_chapter if lvl == 3 else title,
                "level":          lvl,
            })

    # 计算 related_nodes：同 chapter 下的其他节点 id
    chapter_groups: dict[str, list[str]] = {}
    for n in knowledge_nodes:
        chapter_groups.setdefault(n["chapter"], []).append(n["id"])
    for n in knowledge_nodes:
        same_chapter_ids = chapter_groups.get(n["chapter"], [])
        n["related_nodes"] = [nid for nid in same_chapter_ids if nid != n["id"]]

    if knowledge_nodes:
        for i in range(0, len(knowledge_nodes), 100):
            supabase.table("knowledge_nodes")\
                .upsert(knowledge_nodes[i:i+100], on_conflict="id").execute()
        print(f"✅ 知识树同步完成: {len(knowledge_nodes)} 个节点")
    else:
        print("⚠️  未提取到目录，knowledge_nodes 为空")

    # 预建 page → node_id 映射（O(1) 查找）
    page_to_node = build_page_to_node(toc, knowledge_nodes)

    # ── Step 1.5: 填充 knowledge_nodes.content ───────────────────
    print("\nStep 1.5: 聚合页面内容，填充 knowledge_nodes.content...")
    node_content: dict[str, list[str]] = {}  # node_id → [text segments]
    node_by_id = {n["id"]: n for n in knowledge_nodes}

    for page_num in range(total_pages):
        page = doc[page_num]
        text = re.sub(r'\s+', ' ', page.get_text()).strip()
        if len(text) < MIN_CHUNK_LEN:
            continue
        node_id = page_to_node.get(page_num + 1)
        if node_id and node_id in node_by_id:
            node_content.setdefault(node_id, []).append(text)

    # 批量更新 content
    content_updates = []
    for node_id, texts in node_content.items():
        aggregated = "\n\n".join(texts)
        content_updates.append({"id": node_id, "content": aggregated})

    if content_updates:
        for i in range(0, len(content_updates), 100):
            batch = content_updates[i:i+100]
            for item in batch:
                supabase.table("knowledge_nodes")\
                    .update({"content": item["content"]})\
                    .eq("id", item["id"])\
                    .execute()
        print(f"✅ content 填充完成: {len(content_updates)} 个节点有内容")

        # 同步到本地 knowledge_nodes
        for upd in content_updates:
            if upd["id"] in node_by_id:
                node_by_id[upd["id"]]["content"] = upd["content"]
    else:
        print("⚠️  没有节点获得内容")

    # ── Step 1.55: 提取结构化子节点（疾病类）─────────────────────
    print("\nStep 1.55: 提取疾病节点的结构化子节点...")
    ss_success = 0
    ss_updates = []

    for node in knowledge_nodes:
        content = node.get("content")
        if not content or len(content) < 100:
            continue
        if node.get("type") != "disease":
            continue
        try:
            from textbook_pipeline.extract_knowledge_nodes import extract_structured_sections
            sections = extract_structured_sections(content)
            if sections and len(sections) >= 2:
                ss_updates.append({"id": node["id"], "structured_sections": sections})
                node["structured_sections"] = sections
                ss_success += 1
        except Exception as e:
            pass  # 静默失败，不影响主流程

    if ss_updates:
        for i in range(0, len(ss_updates), 100):
            supabase.table("knowledge_nodes")\
                .upsert(ss_updates[i:i+100], on_conflict="id").execute()
    print(f"✅ 结构化子节点提取完成: {ss_success} 个疾病节点")

    # ── Step 1.6: AI 提取 key_points ──────────────────────────────
    if not skip_ai and AI_API_KEY:
        print("\nStep 1.6: AI 提取 key_points...")
        kp_success = 0
        kp_fail = 0
        kp_updates = []

        for node in knowledge_nodes:
            if not node.get("content"):
                continue
            try:
                key_points = extract_key_points(node["title"], node["content"])
                if key_points:
                    kp_updates.append({"id": node["id"], "key_points": key_points})
                    node["key_points"] = key_points
                    kp_success += 1
                else:
                    kp_fail += 1
            except Exception as e:
                print(f"   ⚠️  key_points 提取异常 [{node['title']}]: {e}")
                kp_fail += 1

        if kp_updates:
            for i in range(0, len(kp_updates), 100):
                supabase.table("knowledge_nodes")\
                    .upsert(kp_updates[i:i+100], on_conflict="id").execute()
        print(f"✅ key_points 提取完成: 成功 {kp_success}, 跳过/失败 {kp_fail}")
    elif skip_ai:
        print("\nStep 1.6: ⏭️  跳过 AI 提取（--skip-ai）")
    else:
        print("\nStep 1.6: ⏭️  AI_API_KEY 未配置，跳过 key_points 提取")

    # ── Step 1.7: AI 生成 causal_links ────────────────────────────
    if not skip_ai and AI_API_KEY:
        print("\nStep 1.7: AI 生成 causal_links...")
        # 按 chapter 分组
        chapter_node_groups: dict[str, list[dict]] = {}
        for node in knowledge_nodes:
            if node.get("content"):
                chapter_node_groups.setdefault(node["chapter"], []).append(node)

        all_causal_links: dict[str, list[dict]] = {}  # node_id → [{from, to, relation}]
        all_chains: list[dict] = []

        for chapter, nodes in chapter_node_groups.items():
            if len(nodes) < 2:
                continue

            # 每批 5-10 个节点
            batch_size = min(max(5, len(nodes) // 3), 10)
            for batch_start in range(0, len(nodes), batch_size):
                batch_nodes = nodes[batch_start:batch_start + batch_size]
                if len(batch_nodes) < 2:
                    continue

                try:
                    links = generate_causal_links(batch_nodes)
                    if not links:
                        continue

                    # 将 links 映射到 node_id
                    title_to_id = {n["title"]: n["id"] for n in batch_nodes}
                    for link in links:
                        from_id = title_to_id.get(link["from"])
                        to_id = title_to_id.get(link["to"])
                        if from_id and to_id:
                            all_causal_links.setdefault(from_id, []).append(link)
                            all_causal_links.setdefault(to_id, []).append(link)

                except Exception as e:
                    print(f"   ⚠️  causal_links 生成异常 [chapter={chapter}]: {e}")

        # 写入 knowledge_nodes.causal_links
        cl_updates = []
        for node_id, links in all_causal_links.items():
            # 去重
            seen = set()
            unique_links = []
            for link in links:
                key = (link["from"], link["to"])
                if key not in seen:
                    seen.add(key)
                    unique_links.append(link)
            cl_updates.append({"id": node_id, "causal_links": unique_links})

        if cl_updates:
            for i in range(0, len(cl_updates), 100):
                supabase.table("knowledge_nodes")\
                    .upsert(cl_updates[i:i+100], on_conflict="id").execute()
            print(f"✅ causal_links 写入完成: {len(cl_updates)} 个节点")

        # 写入 causal_chains 表（将每个 chapter 的因果链汇总为一条 chain）
        for chapter, nodes in chapter_node_groups.items():
            chapter_links = []
            title_to_id = {n["title"]: n["id"] for n in nodes}
            for node in nodes:
                node_links = all_causal_links.get(node["id"], [])
                for link in node_links:
                    if link["from"] in title_to_id and link["to"] in title_to_id:
                        chapter_links.append(link)

            if not chapter_links:
                continue

            # 去重
            seen = set()
            unique_chapter_links = []
            for link in chapter_links:
                key = (link["from"], link["to"])
                if key not in seen:
                    seen.add(key)
                    unique_chapter_links.append(link)

            chain_id = hashlib.md5(f"{textbook_name}_{chapter}_chain".encode()).hexdigest()[:12]
            chain_steps = [
                {
                    "from": link["from"],
                    "to": link["to"],
                    "relation": link["relation"],
                }
                for link in unique_chapter_links
            ]
            related_node_ids = list(set(
                title_to_id.get(link["from"]) or title_to_id.get(link["to"])
                for link in unique_chapter_links
                if title_to_id.get(link["from"]) or title_to_id.get(link["to"])
            ))

            try:
                supabase.table("causal_chains").upsert({
                    "id": chain_id,
                    "title": f"{chapter} - 因果推导链",
                    "steps": chain_steps,
                    "related_nodes": related_node_ids,
                    "source": "textbook_auto",
                }, on_conflict="id").execute()
            except Exception as e:
                print(f"   ⚠️  causal_chains 写入异常 [chapter={chapter}]: {e}")

        print(f"✅ causal_links 处理完成")
    elif skip_ai:
        print("\nStep 1.7: ⏭️  跳过 AI 生成（--skip-ai）")
    else:
        print("\nStep 1.7: ⏭️  AI_API_KEY 未配置，跳过 causal_links 生成")

    # ── Step 2: 读取已入库进度 ─────────────────────────────────────
    existing_indices = fetch_existing_chunk_indices(textbook_name)
    if existing_indices:
        print(f"\nℹ️  检测到已有 {len(existing_indices)} 个 chunk，已自动跳过已完成部分")

    # ── Step 3: 句子感知切片 ──────────────────────────────────────
    print("\nStep 2: 语义切片...")
    pending_chunks = []
    global_idx = 0
    skipped_count = 0

    for page_num in range(total_pages):
        page = doc[page_num]
        text = re.sub(r'\s+', ' ', page.get_text()).strip()
        if len(text) < MIN_CHUNK_LEN:
            continue

        for chunk_text in sentence_aware_chunk(text):
            if global_idx in existing_indices:
                skipped_count += 1
            else:
                related_node_id = page_to_node.get(page_num + 1)
                related_node = node_by_id.get(related_node_id) if related_node_id else None
                pending_chunks.append({
                    "document_name": textbook_name,
                    "content":       chunk_text,
                    "page_number":   page_num + 1,
                    "chunk_index":   global_idx,
                    "chapter":       related_node["chapter"] if related_node else None,
                    "section":       related_node.get("sub_chapter") if related_node else None,
                    "related_node_id": related_node_id,
                    "embedding":     None,  # placeholder, filled later
                })
            global_idx += 1

    if not pending_chunks:
        print("✅ 已全部入库，无需重复处理。")
        doc.close()
        return

    print(f"🚀 待处理 {len(pending_chunks)} 个片段（已跳过 {skipped_count} 个，整书共 {global_idx} 个）")

    # ── Step 4: API 批量向量化 ────────────────────────────────────
    print(f"\nStep 3: API 向量化 (model={EMBED_MODEL}, batch={EMBED_API_BATCH})...")
    total_embedded = 0
    for batch_start in range(0, len(pending_chunks), EMBED_API_BATCH):
        batch_items = pending_chunks[batch_start:batch_start + EMBED_API_BATCH]
        batch_texts = [c["content"] for c in batch_items]

        retry_count = 0
        while retry_count < 3:
            try:
                embeddings = get_embeddings(batch_texts)
                for i, item in enumerate(batch_items):
                    item["embedding"] = embeddings[i]
                total_embedded += len(batch_items)
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= 3:
                    print(f"   ❌ 向量化失败 [{batch_start}-{batch_start+len(batch_items)}]: {e}")
                    # 将失败的 chunk 的 embedding 设为 None，后续跳过
                    for item in batch_items:
                        item["embedding"] = None
                else:
                    print(f"   ⚠️  重试 {retry_count}/3: {e}")
                    time.sleep(2)

        if total_embedded % 200 < EMBED_API_BATCH:
            print(f"   📊 已向量化: {total_embedded}/{len(pending_chunks)}")

    # 过滤掉向量化失败的 chunk
    valid_chunks = [c for c in pending_chunks if c.get("embedding") is not None]
    failed_embed = len(pending_chunks) - len(valid_chunks)
    if failed_embed > 0:
        print(f"   ⚠️  {failed_embed} 个片段向量化失败，将跳过")
    pending_chunks = valid_chunks

    # ── Step 5: 写 Supabase ──────────────────────────────────────
    print("\nStep 4: 写入数据库（带重试）...")
    batches    = [pending_chunks[i:i+DB_BATCH] for i in range(0, len(pending_chunks), DB_BATCH)]
    total_ok   = 0
    total_fail = 0
    failed_batches: list[int] = []

    for batch_idx, batch in enumerate(batches):
        try:
            total_ok += write_batch_to_db(batch, batch_idx)
            print(f"   ✅ batch {batch_idx+1}/{len(batches)}  累计: {total_ok}")
        except Exception as e:
            total_fail += len(batch)
            failed_batches.append(batch_idx + 1)
            print(f"   ❌ batch {batch_idx+1} 最终失败: {e}")

    doc.close()
    print(f"\n{'='*60}")
    print(f"🎉 《{textbook_name}》入库完成！")
    print(f"   知识点: {len(knowledge_nodes)}  文本块: {total_ok}  失败: {total_fail}")
    print(f"{'='*60}")

    if total_fail > 0:
        print(f"⚠️  以下 batch 写入失败: {failed_batches}")
        raise SystemExit(1)


# ── 入口 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    skip_ai_flag = "--skip-ai" in sys.argv
    args       = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print("用法: python ingest_final.py <PDF路径> [--reset] [--skip-ai]")
        print("示例: python ingest_final.py F:/ml/textbook/内科学（第10版）.pdf")
        print("      python ingest_final.py F:/ml/textbook/内科学（第10版）.pdf --reset")
        print("      python ingest_final.py F:/ml/textbook/内科学（第10版）.pdf --skip-ai")
        sys.exit(1)

    process_textbook(args[0], reset=reset_flag, skip_ai=skip_ai_flag)

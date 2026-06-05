import os
import fitz
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

load_dotenv(dotenv_path='../.env')

SUPABASE_URL = os.getenv("TARO_APP_SUPABASE_URL")
SUPABASE_KEY = os.getenv("TARO_APP_SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 加载本地 GTE 模型 (维度 768)
print("正在加载本地向量模型 (GTE-Base-ZH)...")
model = SentenceTransformer('iic/nlp_gte_sentence-embedding_chinese-base')

def process_full_book(pdf_path):
    doc = fitz.open(pdf_path)
    textbook_name = "内科学（第10版）"

    # --- 1. 提取目录并生成知识树节点 ---
    print("正在提取目录结构...")
    toc = doc.get_toc() # [[lvl, title, page], ...]
    nodes = []
    current_subject = ""
    current_chapter = ""

    for lvl, title, page in toc:
        clean_title = title.replace('\n', '').strip()
        if lvl == 1:
            current_subject = clean_title
        elif lvl == 2:
            current_chapter = clean_title
        elif lvl == 3:
            # 第三层级通常是具体疾病或知识点
            nodes.append({
                "id": f"node_{textbook_name}_{page}_{len(nodes)}",
                "title": clean_title,
                "subject": current_subject,
                "chapter": current_chapter,
                "type": "disease" if "病" in clean_title or "炎" in clean_title else "concept",
                "source": "textbook_auto",
                "textbook": textbook_name
            })

    if nodes:
        print(f"提取到 {len(nodes)} 个核心知识点。正在同步到 knowledge_nodes...")
        # 批量插入知识点节点
        for i in range(0, len(nodes), 100):
            supabase.table("knowledge_nodes").upsert(nodes[i:i+100]).execute()

    # --- 2. 全书切片向量化 (RAG Chunks) ---
    print("正在进行全书切片向量化...")
    all_chunks = []
    chunk_size = 600
    overlap = 120

    for page_num, page in enumerate(doc):
        text = page.get_text().replace('\n', ' ')
        if len(text) < 100: continue

        for i in range(0, len(text), chunk_size - overlap):
            chunk_content = text[i:i + chunk_size]
            if len(chunk_content) < 50: continue

            all_chunks.append({
                "document_name": textbook_name,
                "content": chunk_content,
                "page_number": page_num + 1,
                "chunk_index": len(all_chunks)
            })

    print(f"全书拆解为 {len(all_chunks)} 个语义片段。开始同步向量数据...")

    # 批量生成向量并上传
    for i in range(0, len(all_chunks), 50):
        batch = all_chunks[i:i + 50]
        contents = [c['content'] for c in batch]
        embeddings = model.encode(contents, normalize_embeddings=True)

        for idx, item in enumerate(batch):
            item['embedding'] = embeddings[idx].tolist()

        supabase.table("document_chunks").insert(batch).execute()
        if i % 100 == 0:
            print(f"已完成: {i}/{len(all_chunks)}")

    print("✅ 整本书已全部拆解并同步至云端知识库！")

if __name__ == "__main__":
    PDF_PATH = "G:/MedLearn/textbook/内科学（第10版）.pdf"
    process_full_book(PDF_PATH)

import os
import fitz  # PyMuPDF
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer

# 加载环境变量
load_dotenv(dotenv_path='../.env')

SUPABASE_URL = os.getenv("TARO_APP_SUPABASE_URL")
SUPABASE_KEY = os.getenv("TARO_APP_SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. 加载本地模型 (请修改为你的本地模型路径)
# 确保模型的 dimension 与数据库中的 VECTOR(384) 一致
print("正在加载本地向量模型...")
model = SentenceTransformer('BAAI/bge-small-zh-v1.5')

def extract_chunks_from_pdf(pdf_path, chunk_size=500, overlap=100):
    """
    从 PDF 提取文本并进行语义分片
    chunk_size: 每个片段的字数
    overlap: 片段之间的重叠字数，确保上下文不丢失
    """
    doc = fitz.open(pdf_path)
    textbook_name = os.path.basename(pdf_path)
    all_chunks = []

    for page_num, page in enumerate(doc):
        text = page.get_text().replace('\n', ' ')
        # 简单的滑动窗口分片
        for i in range(0, len(text), chunk_size - overlap):
            chunk_content = text[i:i + chunk_size]
            if len(chunk_content) < 50: continue # 过滤太短的片段

            all_chunks.append({
                "document_name": textbook_name,
                "content": chunk_content,
                "page_number": page_num + 1,
                "chunk_index": len(all_chunks)
            })
    return all_chunks

def ingest(pdf_path):
    # 提取
    print(f"正在分析教材: {pdf_path}")
    chunks = extract_chunks_from_pdf(pdf_path)

    # 生成向量
    print(f"正在为 {len(chunks)} 个片段生成向量...")
    contents = [c['content'] for c in chunks]
    embeddings = model.encode(contents, normalize_embeddings=True)

    # 组装数据
    data = []
    for i, chunk in enumerate(chunks):
        chunk['embedding'] = embeddings[i].tolist()
        data.append(chunk)

    # 批量上传到 Supabase (每 50 条一组，防止请求过大)
    batch_size = 50
    print("正在同步到云端数据库...")
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        supabase.table("document_chunks").insert(batch).execute()
        print(f"已进度: {i + len(batch)}/{len(data)}")

if __name__ == "__main__":
    # 使用示例：将你的 PDF 路径放在这里
    target_pdf = "G:/path/to/your/textbook.pdf"
    if os.path.exists(target_pdf):
        ingest(target_pdf)
    else:
        print(f"请在脚本中设置正确的 PDF 路径: {target_pdf}")

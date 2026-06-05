import os
import sys
from dotenv import load_dotenv
from supabase import create_client

def check_env():
    print("--- MedLearn 环境检查 ---")

    # 1. 检查环境变量
    load_dotenv(dotenv_path='../.env')
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print("❌ 错误: .env 文件中缺失 SUPABASE_URL 或 SUPABASE_ANON_KEY")
        return
    else:
        print(f"✅ 环境变量已读取: {url[:20]}...")

    # 2. 检查 Supabase 连接
    try:
        supabase = create_client(url, key)
        # 尝试读取一个表头来验证连接
        supabase.table("knowledge_nodes").select("count", count="exact").limit(1).execute()
        print("✅ Supabase 数据库连接成功!")
    except Exception as e:
        print(f"❌ Supabase 连接失败: {e}")
        print("提示: 请检查 URL 和 Key 是否正确，以及网络是否通畅。")
        return

    # 3. 检查必要库
    try:
        import fitz
        print("✅ PyMuPDF (fitz) 已安装")
        from sentence_transformers import SentenceTransformer
        print("✅ sentence-transformers 已安装")
    except ImportError as e:
        print(f"❌ 缺失必要库: {e}")
        print("请运行: pip install pymupdf sentence-transformers supabase python-dotenv")
        return

    # 4. 检查模型 (可选)
    print("正在尝试加载模型 (首次加载可能较慢)...")
    try:
        model = SentenceTransformer('iic/nlp_gte_sentence-embedding_chinese-base')
        dim = model.get_sentence_embedding_dimension()
        print(f"✅ 模型加载成功! 向量维度: {dim}")
        if dim != 768:
            print(f"⚠️ 警告: 模型维度为 {dim}，但预期为 768。请确保数据库 SQL 与之匹配。")
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")

    print("\n--- 检查完成! 如果上面都是 ✅，你可以放心运行 ingest_with_tree.py 了 ---")

if __name__ == "__main__":
    check_env()

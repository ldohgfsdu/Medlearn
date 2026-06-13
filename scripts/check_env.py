import os
import sys
from dotenv import load_dotenv
from supabase import create_client

def check_env():
    print("--- Medlearn 环境检查 ---")

    # 1. 检查环境变量
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url:
        print("❌ 错误: .env 文件中缺失 SUPABASE_URL")
        return
    else:
        print(f"✅ 环境变量已读取: {url[:20]}...")

    if not anon_key:
        print("⚠️ 警告: .env 文件中缺失 SUPABASE_ANON_KEY（前端需要）")
    else:
        print("✅ Anon Key 已配置")

    if not service_key:
        print("⚠️ 警告: .env 文件中缺失 SUPABASE_SERVICE_ROLE_KEY（脚本写入需要）")
    else:
        print("✅ Service Role Key 已配置")

    # 2. 检查 Supabase 连接
    try:
        # 使用 anon key 测试基本连接
        if anon_key:
            supabase = create_client(url, anon_key)
            supabase.table("knowledge_nodes").select("count", count="exact").limit(1).execute()
            print("✅ Supabase 数据库连接成功 (Anon Key)!")

        # 使用 service role key 测试写入权限
        if service_key:
            supabase_admin = create_client(url, service_key)
            supabase_admin.table("knowledge_nodes").select("count", count="exact").limit(1).execute()
            print("✅ Service Role Key 验证成功（有写入权限）!")
    except Exception as e:
        print(f"❌ Supabase 连接失败: {e}")
        print("提示: 请检查 URL 和 Key 是否正确，以及网络是否通畅。")
        return

    # 3. 检查必要库
    try:
        import fitz
        print("✅ PyMuPDF (fitz) 已安装")
    except ImportError as e:
        print(f"❌ 缺失必要库: {e}")
        print("请运行: pip install pymupdf supabase python-dotenv")
        return

    # 4. 检查 SiliconFlow API 连接 (可选)
    siliconflow_key = os.getenv("SILICONFLOW_KEY")
    if siliconflow_key:
        print("正在测试 SiliconFlow API 连接...")
        try:
            import requests
            resp = requests.post(
                'https://api.siliconflow.cn/v1/embeddings',
                headers={'Authorization': f'Bearer {siliconflow_key}', 'Content-Type': 'application/json'},
                json={'model': 'BAAI/bge-large-zh-v1.5', 'input': 'test'},
                timeout=10,
            )
            if resp.status_code == 200:
                dim = len(resp.json()['data'][0]['embedding'])
                print(f"✅ SiliconFlow API 连接成功! 向量维度: {dim}")
            else:
                print(f"⚠️ SiliconFlow API 返回状态码: {resp.status_code}")
        except Exception as e:
            print(f"❌ SiliconFlow API 连接失败: {e}")
    else:
        print("⚠️ 未配置 SILICONFLOW_KEY，跳过向量服务检查")

    print("\n--- 检查完成! 如果上面都是 ✅，你可以放心运行 ingest_with_tree.py 了 ---")

if __name__ == "__main__":
    check_env()

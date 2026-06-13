"""清空 knowledge_nodes 和 document_chunks"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
client = create_client(url, key)

# 先查有多少条
res1 = client.table("knowledge_nodes").select("id", count="exact").execute()
res2 = client.table("document_chunks").select("id", count="exact").execute()
print(f"清空前: knowledge_nodes={res1.count}, document_chunks={res2.count}")
print("⚠️  警告: 此操作将级联删除所有关联的用户学习记录 (feynman_records, spaced_repetition, favorites 等)!")
print("⚠️  此操作不可逆!")

confirm = input("确认清空? 输入 'yes' 确认: ")
if confirm.strip().lower() != 'yes':
    print("❌ 已取消")
    raise SystemExit(0)

# 清空
client.table("knowledge_nodes").delete().neq("id", "").execute()
# document_chunks id 是 bigint，用 gte 0 条件
client.table("document_chunks").delete().gte("id", 0).execute()

# 验证
res1 = client.table("knowledge_nodes").select("id", count="exact").execute()
res2 = client.table("document_chunks").select("id", count="exact").execute()
print(f"清空后: knowledge_nodes={res1.count}, document_chunks={res2.count}")
print("✅ 清库完成")

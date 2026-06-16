# RAG系统设置指南

**版本**: 1.0  
**日期**: 2026-06-03  
**状态**: 可用

---

## 目录

1. [系统概述](#1-系统概述)
2. [环境准备](#2-环境准备)
3. [数据库设置](#3-数据库设置)
4. [文档索引](#4-文档索引)
5. [问答服务](#5-问答服务)
6. [测试验证](#6-测试验证)
7. [常见问题](#7-常见问题)

---

## 1. 系统概述

### 1.1 什么是RAG？

RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合检索和生成的AI问答系统：

```
用户提问 → 向量检索相关文档片段 → 拼接上下文 + 提问 → LLM生成回答
```

### 1.2 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG 系统架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  PDF文档  │───▶│  文档分块  │───▶│  向量化   │             │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │               │               │                     │
│       ▼               ▼               ▼                     │
│  ┌──────────────────────────────────────┐                  │
│  │         Supabase (pgvector)          │                  │
│  │         向量存储 + 检索               │                  │
│  └──────────────────────────────────────┘                  │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  用户提问  │───▶│  向量检索  │───▶│  LLM问答  │             │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 核心组件

| 组件 | 作用 | 技术选型 |
|------|------|----------|
| 文档分块 | 将PDF文本切成小段 | PyMuPDF + 自定义分块器 |
| 向量化 | 将文本转为向量用于语义搜索 | OpenAI `text-embedding-3-small` |
| 向量数据库 | 存储和检索向量 | Supabase pgvector扩展 |
| LLM问答 | 根据检索结果生成回答 | GPT-4o / Claude |

---

## 2. 环境准备

### 2.1 安装Python依赖

```bash
cd g:\ml
pip install -r requirements-rag.txt
```

### 2.2 配置环境变量

在 `.env` 文件中添加以下配置：

```env
# Supabase配置（已有）
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# OpenAI API配置（需要添加）
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o

# Anthropic配置（可选）
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 2.3 获取API密钥

#### OpenAI API密钥

1. 访问 [OpenAI Platform](https://platform.openai.com/)
2. 注册/登录账号
3. 进入 API Keys 页面
4. 创建新的API密钥
5. 复制密钥到 `.env` 文件

#### Supabase配置

1. 访问 [Supabase Dashboard](https://supabase.com/dashboard)
2. 选择你的项目
3. 进入 Settings > API
4. 复制 URL 和 anon key

---

## 3. 数据库设置

### 3.1 运行Migration

在Supabase Dashboard中运行SQL migration：

1. 进入 Supabase Dashboard
2. 选择你的项目
3. 进入 SQL Editor
4. 复制 `supabase/migrations/002_enable_pgvector.sql` 的内容
5. 点击 "Run" 执行

### 3.2 验证设置

```sql
-- 检查pgvector扩展是否启用
SELECT * FROM pg_extension WHERE extname = 'vector';

-- 检查document_chunks表是否创建
SELECT * FROM document_chunks LIMIT 1;

-- 检查检索函数是否创建
SELECT * FROM pg_proc WHERE proname = 'match_documents';
```

---

## 4. 文档索引

### 4.1 索引单个PDF文档

```bash
cd g:\ml

# 基本用法
python scripts/embed_pdf.py --pdf textbook/辅导讲义中册.pdf

# 自定义参数
python scripts/embed_pdf.py \
  --pdf textbook/辅导讲义中册.pdf \
  --chunk-size 800 \
  --chunk-overlap 200 \
  --batch-size 100

# 预览模式（不入库）
python scripts/embed_pdf.py --pdf textbook/辅导讲义中册.pdf --dry-run
```

### 4.2 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--pdf` | 必需 | PDF文件路径 |
| `--chunk-size` | 800 | 每个chunk的目标token数 |
| `--chunk-overlap` | 200 | chunk之间的重叠token数 |
| `--batch-size` | 100 | 每批处理的chunk数量 |
| `--dry-run` | false | 只预览不入库 |

### 4.3 索引多个文档

```bash
# 索引所有PDF文档
for pdf in textbook/*.pdf; do
  python scripts/embed_pdf.py --pdf "$pdf"
done
```

### 4.4 查看已索引文档

```sql
-- 在Supabase SQL Editor中执行
SELECT * FROM document_stats;
```

---

## 5. 问答服务

### 5.1 TypeScript服务（前端）

```typescript
import { DocumentQAService } from './services/documentQA'

// 完整问答
const response = await DocumentQAService.ask({
  question: '肺炎的临床表现有哪些？',
  document_name: '辅导讲义中册',  // 可选，指定文档
  top_k: 5,                       // 可选，返回结果数量
  temperature: 0.3                // 可选，LLM温度参数
})

console.log('回答:', response.answer)
console.log('来源:', response.sources)
```

### 5.2 Supabase Edge Function 调用

```javascript
// 调用 Edge Function
const { data: result } = await supabase.functions.invoke('documentQA', {
  body: {
    action: 'ask',
    question: '肺炎的临床表现有哪些？',
    document_name: '辅导讲义中册',
    top_k: 5,
    temperature: 0.3
  }
})

if (result.result.success) {
  console.log('回答:', result.result.data.answer)
  console.log('来源:', result.result.data.sources)
}
```

### 5.3 支持的操作

| 操作 | 说明 | 参数 |
|------|------|------|
| `ask` | 完整问答 | question, document_name?, top_k?, temperature? |
| `search` | 只检索不生成回答 | question, document_name?, top_k? |
| `documents` | 获取文档列表 | 无 |
| `stats` | 获取文档统计 | document_name |

---

## 6. 测试验证

### 6.1 运行测试脚本

```bash
cd g:\ml
python scripts/test_rag.py
```

### 6.2 测试内容

测试脚本会验证：

1. ✓ Embedding API连接
2. ✓ Supabase连接
3. ✓ 向量检索功能
4. ✓ Chat API连接
5. ✓ 完整RAG流程

### 6.3 手动测试

```bash
# 1. 测试Embedding API
python -c "
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
response = client.embeddings.create(model='text-embedding-3-small', input='测试')
print('Embedding维度:', len(response.data[0].embedding))
"

# 2. 测试Supabase连接
python -c "
from supabase import create_client
import os
from dotenv import load_dotenv
load_dotenv()
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
result = client.table('document_chunks').select('count', count='exact').execute()
print('记录数:', result.count)
"
```

---

## 7. 常见问题

### 7.1 Embedding API错误

**问题**: `Authentication Error: Invalid API Key`

**解决**:
1. 检查 `.env` 文件中的 `OPENAI_API_KEY` 是否正确
2. 确认API密钥是否有效
3. 检查账户是否有足够余额

### 7.2 Supabase连接错误

**问题**: `Connection refused` 或 `Invalid URL`

**解决**:
1. 检查 `.env` 文件中的 `SUPABASE_URL` 是否正确
2. 确认Supabase项目是否正常运行
3. 检查网络连接

### 7.3 pgvector扩展未启用

**问题**: `function match_documents does not exist`

**解决**:
1. 在Supabase SQL Editor中运行 `002_enable_pgvector.sql`
2. 确认扩展已启用：`SELECT * FROM pg_extension WHERE extname = 'vector';`

### 7.4 向量检索返回空结果

**问题**: 检索函数返回空数组

**解决**:
1. 确认文档已成功索引：`SELECT * FROM document_chunks LIMIT 10;`
2. 检查向量是否正确生成：`SELECT id, embedding IS NOT NULL as has_embedding FROM document_chunks LIMIT 10;`
3. 尝试降低相似度阈值

### 7.5 LLM回答不准确

**问题**: 回答与文档内容不符

**解决**:
1. 增加 `top_k` 参数，获取更多相关片段
2. 降低 `temperature` 参数，提高回答准确性
3. 优化系统提示词（修改 `documentQA.ts` 中的 `systemPrompt`）

### 7.6 处理速度慢

**问题**: 文档索引或问答响应慢

**解决**:
1. 减小 `chunk-size` 参数
2. 增加 `batch-size` 参数
3. 使用更快的Embedding模型
4. 考虑使用本地Embedding模型（如 `sentence-transformers`）

---

## 8. 高级配置

### 8.1 使用本地Embedding模型

如果你想使用本地模型（无需API费用）：

```python
# 安装依赖
pip install sentence-transformers

# 修改 embed_pdf.py 中的 EmbeddingGenerator 类
from sentence_transformers import SentenceTransformer

class LocalEmbeddingGenerator:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
    
    def generate_embeddings(self, texts):
        return self.model.encode(texts).tolist()
```

### 8.2 使用Anthropic Claude

如果你 prefer 使用Claude：

```env
# .env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
CHAT_MODEL=claude-3-sonnet-20240229
```

修改 `documentQA.ts` 中的 `generateAnswer` 函数使用Anthropic API。

### 8.3 自定义分块策略

修改 `embed_pdf.py` 中的 `PDFChunker` 类：

```python
class CustomPDFChunker(PDFChunker):
    def split_text_into_chunks(self, text, page_number):
        # 按段落分块
        paragraphs = text.split('\n\n')
        chunks = []
        for para in paragraphs:
            if len(para.strip()) > 50:  # 过滤太短的段落
                chunks.append({
                    "content": para.strip(),
                    "page_number": page_number,
                    "token_count": self.count_tokens(para)
                })
        return chunks
```

---

## 9. 性能优化

### 9.1 批量处理

```bash
# 使用更大的batch-size
python scripts/embed_pdf.py --pdf textbook/辅导讲义中册.pdf --batch-size 200
```

### 9.2 并行处理

```python
# 使用多进程处理
from multiprocessing import Pool

def process_chunk(chunk):
    # 处理单个chunk
    pass

with Pool(4) as p:
    results = p.map(process_chunk, chunks)
```

### 9.3 缓存Embedding

```python
# 缓存已生成的embedding
import hashlib
import json

def get_cached_embedding(text, cache_file='embedding_cache.json'):
    # 计算文本hash
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    # 检查缓存
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache = json.load(f)
            if text_hash in cache:
                return cache[text_hash]
    
    # 生成新的embedding
    embedding = generate_embedding(text)
    
    # 保存到缓存
    cache[text_hash] = embedding
    with open(cache_file, 'w') as f:
        json.dump(cache, f)
    
    return embedding
```

---

## 10. 监控和日志

### 10.1 查看索引进度

```sql
-- 查看文档索引统计
SELECT 
  document_name,
  COUNT(*) as chunk_count,
  MIN(page_number) as min_page,
  MAX(page_number) as max_page,
  COUNT(DISTINCT chapter) as chapter_count,
  MIN(created_at) as indexed_at
FROM document_chunks
GROUP BY document_name
ORDER BY indexed_at DESC;
```

### 10.2 查看查询日志

```sql
-- 查看最近的查询（需要自行实现日志表）
SELECT * FROM query_logs 
ORDER BY created_at DESC 
LIMIT 100;
```

---

## 附录

### A. 完整示例代码

```python
# 完整的问答流程示例
from openai import OpenAI
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

# 初始化客户端
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
supabase_client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

def ask_question(question, document_name=None, top_k=5):
    # 1. 生成查询向量
    response = openai_client.embeddings.create(
        model='text-embedding-3-small',
        input=question
    )
    embedding = response.data[0].embedding
    
    # 2. 检索相关文档
    params = {
        'query_embedding': embedding,
        'match_count': top_k
    }
    if document_name:
        params['filter_document'] = document_name
    
    search_result = supabase_client.rpc('match_documents', params).execute()
    
    if not search_result.data:
        return "没有找到相关文档内容"
    
    # 3. 拼接上下文
    context = "\n\n".join([
        f"--- 片段 {i+1} [页码: {item.get('page_number', '未知')}] ---\n{item['content']}"
        for i, item in enumerate(search_result.data)
    ])
    
    # 4. 调用LLM生成回答
    chat_response = openai_client.chat.completions.create(
        model='gpt-4o',
        messages=[
            {
                'role': 'system',
                'content': f'你是一个医学文档助手。请根据以下文档片段回答问题。\n\n文档片段：\n{context}'
            },
            {'role': 'user', 'content': question}
        ],
        temperature=0.3,
        max_tokens=2000
    )
    
    return chat_response.choices[0].message.content

# 使用示例
answer = ask_question('肺炎的临床表现有哪些？', '辅导讲义中册')
print(answer)
```

### B. 相关资源

- **OpenAI API文档**: https://platform.openai.com/docs
- **Supabase文档**: https://supabase.com/docs
- **pgvector文档**: https://github.com/pgvector/pgvector
- **RAG最佳实践**: https://docs.llamaindex.ai/en/stable/optimizing/production_rag.html

---

*文档结束。如有问题请联系开发团队。*

"""快速测试 AI 提炼 - 只处理一个知识点"""
import json
import urllib.request
import urllib.error
from pathlib import Path

SYSTEM_PROMPT = """你是一位资深的医学教育专家，善于将教材提炼为简洁的知识卡片。

## 输出格式（纯JSON）
{
  "definition": "1句话精确定义，不超过50字",
  "keyPoints": [
    "重点1 不超过60字",
    "重点2 不超过60字",
    "重点3 不超过60字",
    "重点4 不超过60字",
    "重点5 不超过60字"
  ],
  "memoryAid": "记忆口诀或理解方法",
  "clinicalPearls": "临床上有何意义"
}

要求：大幅压缩，只输出JSON，不要额外解释"""

config = json.loads(Path('.api_config.json').read_text())

nodes_file = Path('generated/textbook/physiology-10-v13/nodes.staging.json')
data = json.loads(nodes_file.read_text(encoding='utf-8'))
node = data['nodes'][0]

content = node['content']
if len(content) > 4000:
    content = content[:4000]

prompt = f"""知识点: {node['title']} ({node.get('chapter', '')})

教材原文:
{content}"""

print(f'提炼中... {node["title"]}')
print(f'原文长度: {len(node["content"])} 字符')
print()

body = json.dumps({
    'model': config['model'],
    'messages': [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': prompt},
    ],
    'max_tokens': 2000,
    'temperature': 0.3,
}).encode('utf-8')

req = urllib.request.Request(
    f"{config['base_url']}/chat/completions",
    data=body,
    headers={
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {config['api_key']}",
    },
)

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        text = result['choices'][0]['message']['content']
        print('=== AI 返回 ===')
        print(text)

        parsed = json.loads(text.strip()) if text.strip().startswith('{') else None
        if not parsed:
            import re
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                parsed = json.loads(m.group())

        if parsed:
            print('\n=== 对比 ===')
            print(f'原文: {len(node["content"])} 字符')
            print(f'定义: {parsed.get("definition", "")}')
            print(f'重点: {len(parsed.get("keyPoints", []))} 条')
            print(f'口诀: {parsed.get("memoryAid", "")[:50]}...')
            print(f'\n压缩比: {len(json.dumps(parsed, ensure_ascii=False)) / len(node["content"]) * 100:.1f}%')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}: {e.read().decode()[:500]}')
except Exception as e:
    print(f'错误: {e}')

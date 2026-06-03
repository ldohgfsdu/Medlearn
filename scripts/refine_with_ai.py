"""用 AI 将教材原文提炼为结构化的知识点。

每个知识点包含：
- definition: 1-2 句话的精简定义
- keyPoints: 3-5 个考试重点
- memoryAid: 记忆口诀或理解方法
- clinicalPearls: 临床联系
- difficulty: 难度 (1-3)
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SYSTEM_PROMPT = """你是一位资深的医学教育专家，精通临床医学教材，善于将复杂的医学知识提炼为简洁、易记、考试导向的知识卡片。

## 任务
将给定的教材原文内容提炼为结构化的知识卡片。不要复制原文，要用自己的理解重新组织。

## 输出格式（JSON）
{
  "definition": "1-2句话精确定义，不超过80字",
  "keyPoints": [
    "考试重点1，一句话，不超过40字",
    "考试重点2",
    "考试重点3",
    "考试重点4",
    "考试重点5"
  ],
  "memoryAid": "一个记忆口诀、比喻或推导逻辑，帮助理解和记忆",
  "clinicalPearls": "这个知识点在临床上有什么用？联系临床实际，1-2句话"
}

## 要求
1. 大幅压缩 - 输出应该是原文的5-10%
2. 考试导向 - keyPoints 要对应执医/考研的高频考点
3. 易记 - memoryAid 要有创意、有趣、便于记忆
4. 临床联系 - clinicalPearls 要点明临床意义
5. 只输出JSON，不要额外解释
6. 如果原文内容无法提取有效信息，definition 用 "无"
"""


def load_api_config() -> tuple[str, str, str]:
    config_path = ROOT / '.api_config.json'
    if config_path.exists():
        config = json.loads(config_path.read_text())
        return config.get('base_url', 'http://127.0.0.1:11434/v1'), config.get('api_key', 'ollama'), config.get('model', 'qwen2.5:7b')
    return 'http://127.0.0.1:11434/v1', 'ollama', 'qwen2.5:7b'


def call_ai(base_url: str, api_key: str, model: str, prompt: str, system: str) -> str:
    import urllib.request
    import urllib.error

    data = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt},
        ],
        'max_tokens': 2000,
        'temperature': 0.3,
    }).encode('utf-8')

    req = urllib.request.Request(
        f'{base_url}/chat/completions',
        data=data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result['choices'][0]['message']['content']
    except Exception as e:
        print(f'  API 调用失败: {e}')
        return ''


def extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    import re
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def main():
    base_url, api_key, model = load_api_config()
    print(f'API: {base_url}, 模型: {model}')

    nodes_file = Path('generated/textbook/physiology-10-v13/nodes.staging.json')
    if not nodes_file.exists():
        print(f'文件不存在: {nodes_file}')
        sys.exit(1)

    data = json.loads(nodes_file.read_text(encoding='utf-8'))
    nodes = data['nodes']

    output_file = Path('generated/textbook/physiology-10-v13/nodes.refined.json')

    refined = []
    for i, node in enumerate(nodes):
        print(f'[{i+1}/{len(nodes)}] {node["title"]} ...', end=' ', flush=True)

        content = node['content']
        if len(content) > 3000:
            content = content[:3000] + '...(已截断)'

        prompt = f"""知识点名称: {node['title']}
章节: {node.get('chapter', '')}
教材原文: 

{content}"""

        result = call_ai(base_url, api_key, model, prompt, SYSTEM_PROMPT)

        parsed = extract_json(result) if result else None

        if parsed:
            new_node = {
                **{k: v for k, v in node.items() if k != 'content'},
                'definition': parsed.get('definition', ''),
                'keyPoints': parsed.get('keyPoints', node.get('keyPoints', [])),
                'memoryAid': parsed.get('memoryAid', ''),
                'clinicalPearls': parsed.get('clinicalPearls', ''),
                'rawContent': node['content'][:500],
                'aiRefined': True,
            }
            def_text = parsed.get('definition', '')[:40]
            print(f'✓ 定义:{def_text}...')
        else:
            new_node = node
            print('✗ 提取失败')

        refined.append(new_node)
        time.sleep(1)

    output_file.write_text(
        json.dumps({'nodes': refined}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'\n已保存到 {output_file}')


if __name__ == '__main__':
    main()

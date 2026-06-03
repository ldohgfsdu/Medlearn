import json
from pathlib import Path

def main():
    refined_file = Path('generated/textbook/physiology-10-v13/nodes.refined.json')
    data = json.loads(refined_file.read_text(encoding='utf-8'))
    nodes = data['nodes']

    public_dir = Path('public')
    extracted_file = public_dir / 'extracted-knowledge.json'

    refined_nodes = []
    for node in nodes:
        new_node = {
            'id': node['id'],
            'type': node['type'],
            'title': node['title'],
            'subject': node['subject'],
            'chapter': node['chapter'],
            'content': node.get('definition', '') or node.get('content', ''),
            'keyPoints': node.get('keyPoints', []),
            'causalLinks': node.get('causalLinks', []),
            'relatedNodes': node.get('relatedNodes', []),
            'difficulty': node.get('difficulty', 2),
            'tags': node.get('tags', []),
            'source': 'textbook-ai-refined',
            'sourceBook': '生理学（第10版）',
            'memoryAid': node.get('memoryAid', ''),
            'clinicalPearls': node.get('clinicalPearls', ''),
            'sourceSpan': node.get('sourceSpan', {}),
            'createdAt': 1780280000000,
            'updatedAt': 1780280000000,
        }
        refined_nodes.append(new_node)

    stats = {
        'total': len(refined_nodes),
        'withMemoryAid': sum(1 for n in refined_nodes if n['memoryAid']),
        'withClinicalPearls': sum(1 for n in refined_nodes if n['clinicalPearls']),
        'avgKeyPoints': sum(len(n['keyPoints']) for n in refined_nodes) / len(refined_nodes),
        'avgContentLen': sum(len(n['content']) for n in refined_nodes) / len(refined_nodes),
    }

    extracted_file.write_text(
        json.dumps(refined_nodes, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    print(f'导入 {len(refined_nodes)} 个 AI 提炼知识点')
    print(f'有记忆口诀: {stats["withMemoryAid"]}')
    print(f'有临床联系: {stats["withClinicalPearls"]}')
    print(f'平均重点数: {stats["avgKeyPoints"]:.1f}')
    print(f'平均定义长度: {stats["avgContentLen"]:.0f} 字符')

if __name__ == '__main__':
    main()

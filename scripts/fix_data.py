import json
from pathlib import Path

def main():
    public_dir = Path('public')
    extracted_file = public_dir / 'extracted-knowledge.json'
    
    if extracted_file.exists():
        existing = json.loads(extracted_file.read_text(encoding='utf-8'))
    else:
        existing = []
    
    existing = [n for n in existing if not n.get('id', '').startswith('textbook-') 
                and n.get('source') != 'ai-generated']
    
    nodes_file = Path('generated/textbook/physiology-10-v13/nodes.staging.json')
    if nodes_file.exists():
        data = json.loads(nodes_file.read_text(encoding='utf-8'))
        for node in data['nodes']:
            new_node = {
                'id': node['id'],
                'type': node['type'],
                'title': node['title'],
                'subject': node['subject'],
                'chapter': node['chapter'],
                'content': node['content'],
                'keyPoints': node.get('keyPoints', []),
                'causalLinks': node.get('causalLinks', []),
                'relatedNodes': node.get('relatedNodes', []),
                'difficulty': node.get('difficulty', 2),
                'tags': node.get('tags', []),
                'source': 'textbook',
                'sourceBook': '生理学（第10版）',
                'sourceSpan': node.get('sourceSpan', {}),
                'createdAt': 1780280000000,
                'updatedAt': 1780280000000,
            }
            if node.get('definition'):
                new_node['definition'] = node['definition']
            if node.get('qaPairs'):
                new_node['qaPairs'] = node['qaPairs']
            existing.append(new_node)
    
    extracted_file.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f'Total nodes: {len(existing)}')

if __name__ == '__main__':
    main()

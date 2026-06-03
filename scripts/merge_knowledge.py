import json
from pathlib import Path

def main():
    public_dir = Path('public')
    extracted_file = public_dir / 'extracted-knowledge.json'
    
    if extracted_file.exists():
        existing = json.loads(extracted_file.read_text(encoding='utf-8'))
    else:
        existing = []
    
    existing = [n for n in existing if not n.get('id', '').startswith('textbook-')]
    existing_ids = {n['id'] for n in existing}
    
    new_nodes = []
    
    nodes_file = Path('generated/textbook/physiology-10-v13/nodes.staging.json')
    if nodes_file.exists():
        data = json.loads(nodes_file.read_text(encoding='utf-8'))
        for node in data['nodes']:
            if node['id'] not in existing_ids:
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
                new_nodes.append(new_node)
    
    if new_nodes:
        all_nodes = existing + new_nodes
        extracted_file.write_text(
            json.dumps(all_nodes, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        print(f'Added {len(new_nodes)} new nodes, total: {len(all_nodes)}')
    else:
        print(f'No new nodes to add, total: {len(existing)}')

if __name__ == '__main__':
    main()

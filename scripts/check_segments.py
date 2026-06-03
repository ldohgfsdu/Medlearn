import json
from pathlib import Path

segments_file = Path('generated/textbook/internal-medicine-10/segments.jsonl')
segs = [json.loads(l) for l in segments_file.open('r', encoding='utf-8')]

print('=== 检查慢性支气管炎的 parentSegmentId ===')
for s in segs:
    if '慢性支气管炎' in s.get('name', ''):
        print(f"name: {s['name']}")
        print(f"segmentId: {s.get('segmentId')}")
        print(f"parentSegmentId: {s.get('parentSegmentId')}")
        print(f"found: {s.get('found')}")
        print()

print('=== 检查急性上呼吸道感染的 children ===')
for s in segs:
    if '急性上呼吸道感染' in s.get('name', '') and '第一节' in s.get('label', ''):
        print(f"name: {s['name']}")
        print(f"segmentId: {s.get('segmentId')}")
        print(f"parentSegmentId: {s.get('parentSegmentId')}")
        print()

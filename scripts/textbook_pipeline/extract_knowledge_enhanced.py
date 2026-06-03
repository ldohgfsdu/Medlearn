import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.textbook_pipeline.atomic_io import atomic_write_json
from scripts.textbook_pipeline.logger import setup_logger, get_logger

DISEASE_PATTERNS = [
    r'[\u4e00-\u9fff]{2,}(?:病|炎|癌|瘤|结核|气胸|综合征|衰竭|高压|哮喘|贫血|梗死|栓塞|溃疡|结石|中毒|失常|硬化|狼疮|紫癜|血友|痛风|中暑|冻僵|淹溺|电击)',
    r'(?:急性|慢性|原发性|继发性|特发性|遗传性|先天性|获得性)[\u4e00-\u9fff]{2,}',
    r'[\u4e00-\u9fff]{2,}(?:肝炎|肾炎|肾病|肺炎|心肌病|心肌炎|脑炎|肠炎|胃炎|关节炎|骨髓瘤|白血病|淋巴瘤)',
    r'(?:类风湿|强直性|系统性|过敏性|自身免疫性|非酒精性|酒精性)[\u4e00-\u9fff]{2,}',
    r'[\u4e00-\u9fff]{2,}(?:高血压|肝硬化|胃癌|肺癌|骨质疏松|肥胖|痛风|中风|心梗|脑梗)',
    r'(?:窦性|房性|室性|房室)[\u4e00-\u9fff]*心律失常',
]
MECHANISM_TOKENS = ['机制', '病理生理', '生化', '分子', '基因', '信号通路', '受体', '离子通道']
SYMPTOM_TOKENS = ['临床表现', '症状', '体征', '疼痛', '发热', '咳嗽', '呼吸困难']
TREATMENT_TOKENS = ['治疗原则', '治疗方法', '药物治疗', '手术治疗', '化疗', '放疗']

EXCLUDE_DISEASE = ['病理', '生理', '病理学', '生理学', '病理生理学', '病原', '病原体', '病毒', '病因', '发病']

CHAPTER_OVERVIEW_KEYWORDS = ['概述', '总论', '分类', '概要', '推荐阅读']

KNOWN_DISEASE_NAMES = [
    '高血压', '肝硬化', '痛风', '胃癌', '肺癌', '肝癌', '乳腺癌', '前列腺癌',
    '病毒性肝炎', '肺结核', '肠结核', '骨质疏松症', '肥胖症', '糖尿病',
    '甲状腺功能亢进症', '甲状腺功能减退症', '甲状腺炎', '甲亢', '甲减',
    '气胸', '胸腔积液', '心包积液', '腹水',
    '主动脉夹层', '心肌梗死', '脑梗死', '脑出血', '中风',
    '尿路感染', '尿毒症', '肾结石', '胆结石',
    '贫血', '白血病', '淋巴瘤', '骨髓瘤',
    '过敏性紫癜', '血小板减少症', '血友病',
    '风湿热', '类风湿关节炎', '系统性红斑狼疮', '系统性硬化症',
    '心律失常', '心房颤动', '心室颤动', '心动过速', '心动过缓',
    '心脏传导阻滞', '心脏骤停', '心脏性猝死',
    '心力衰竭', '呼吸衰竭', '肝衰竭', '肾衰竭',
    '心肌炎', '心肌病', '心内膜炎', '心包炎',
    '肺炎', '支气管炎', '支气管扩张', '肺脓肿', '肺栓塞',
    '胃炎', '肠炎', '胰腺炎', '胆囊炎', '阑尾炎',
    '肝炎', '肾炎', '肾病', '膀胱炎',
    '关节炎', '滑膜炎', '腱鞘炎',
    '脑炎', '脑膜炎', '脊髓炎',
    '血管炎', '动脉炎', '静脉炎',
    '食管癌', '胃癌', '结直肠癌', '胰腺癌', '胆管癌',
    '膀胱癌', '肾癌', '宫颈癌', '卵巢癌', '子宫内膜癌',
    '甲状腺癌', '甲状腺结节',
    'IgA肾病', 'IgG4相关性疾病',
    '急性肾损伤', '慢性肾脏病',
    '慢性阻塞性肺疾病', '支气管哮喘',
    '肺动脉高压', '肺血栓栓塞症',
    '消化性溃疡', '胃食管反流病',
    '炎症性肠病', '溃疡性结肠炎', '克罗恩病',
    '肠易激综合征', '功能性消化不良',
    '肝硬化', '脂肪肝', '酒精性肝病', '药物性肝病',
    '自身免疫性肝炎', '原发性胆汁性胆管炎', '原发性硬化性胆管炎',
    '骨髓增生异常综合征', '再生障碍性贫血', '溶血性贫血',
    '霍奇金淋巴瘤', '非霍奇金淋巴瘤',
    '多发性骨髓瘤', '骨髓增殖性肿瘤',
    '抗磷脂综合征', '干燥综合征', '强直性脊柱炎',
    '贝赫切特病', '大动脉炎', '巨细胞动脉炎',
    '过敏性肺炎', '嗜酸性粒细胞性肺炎', '结节病',
    '特发性肺纤维化', '特发性肺动脉高压',
    '睡眠呼吸暂停', '阻塞性睡眠呼吸暂停',
    '急性呼吸窘迫综合征', '急性呼吸衰竭', '慢性呼吸衰竭',
    '心脏瓣膜病', '主动脉瓣狭窄', '主动脉瓣反流', '二尖瓣狭窄', '二尖瓣反流',
    '先天性心血管病', '房间隔缺损', '室间隔缺损', '动脉导管未闭',
    '感染性心内膜炎', '急性心包炎', '缩窄性心包炎',
    '下肢动脉硬化闭塞症', '静脉血栓症',
    '心血管神经症',
    '急性胰腺炎', '慢性胰腺炎',
    '肝外胆管结石', '胆囊结石', '胆管炎',
    '胆道系统肿瘤', '原发性肝癌',
    '急性肝衰竭',
    '肾小管疾病', '肾血管疾病', '遗传性肾病',
    '狼疮性肾炎', '糖尿病肾脏病', '血管炎肾损害',
    '急性间质性肾炎', '慢性间质性肾炎',
    '缺铁性贫血', '巨幼细胞贫血',
    '急性白血病', '慢性髓系白血病', '慢性淋巴细胞白血病',
    '出血性疾病', '弥散性血管内凝血',
    '垂体瘤', '库欣综合征', '嗜铬细胞瘤',
    '原发性醛固酮增多症', '低血糖症',
    '高尿酸血症', '血脂异常',
    '性发育异常', '多内分泌腺体疾病',
    '神经内分泌肿瘤', '异位激素分泌综合征',
    '特发性炎症性肌病', '纤维肌痛综合征', '痛风',
    '有机磷杀虫药中毒', '急性一氧化碳中毒', '中暑', '冻僵', '淹溺', '电击',
    '高原病',
    '烟草病学概要',
    '严重急性呼吸综合征', '高致病性人禽流感', '2019冠状病毒病',
    '肺军团病', '肺念珠菌病', '肺曲霉病', '肺隐球菌病', '肺孢子菌肺炎',
    '肺淋巴管平滑肌瘤病', '肺泡蛋白沉着症',
    '下丘脑疾病', '垂体前叶疾病', '垂体后叶疾病',
    '甲状腺疾病', '甲状旁腺疾病', '肾上腺疾病',
    '糖尿病酮症酸中毒', '高渗高血糖综合征',
    '抗利尿不适当综合征',
    '非扩张型左心室心肌病', '致心律失常性右心室心肌病', '限制型心肌病', '肥厚型心肌病', '扩张型心肌病',
    '慢性冠状动脉综合征', '急性冠脉综合征',
    '动脉粥样硬化',
    '肿瘤心脏病学',
    '骨关节炎',
    '原发免疫性血小板减少症', '血红蛋白病', '心脏骤停与心脏性猝死',
    '病毒性肝炎', '肺结核', '肠结核',
    '肾小管性酸中毒', 'Fanconi综合征',
    '肾动脉狭窄', '肾动脉栓塞和血栓形成', '小动脉性肾硬化症', '肾静脉血栓形成',
    '常染色体显性遗传性多囊肾病', 'Alport综合征',
    '遗传性球形红细胞增多症', '红细胞葡萄糖-6-磷酸脱氢酶缺乏症',
    '阵发性睡眠性血红蛋白尿症', '真性红细胞增多症', '原发性血小板增多症', '原发性骨髓纤维化',
    '生长激素缺乏性矮小症', '先天性肾上腺皮质增生症', '胰岛素瘤',
    '水、钠代谢失常', '钾代谢失常',
    '性染色体异常疾病', '46,XY性发育异常', '46,XX性发育异常',
    '多发性内分泌腺瘤病', '自身免疫性多内分泌腺综合征',
    '大动脉炎', '巨细胞动脉炎', '结节性多动脉炎', 'ANCA相关血管炎', '贝赫切特病',
    '成人斯蒂尔病', '复发性多软骨炎',
    '农药中毒', '急性毒品中毒', '急性乙醇中毒', '镇静催眠药中毒',
    '急性亚硝酸盐中毒', '有机溶剂中毒', '毒蛇咬伤中毒', '冻僵',
    '阻塞性睡眠呼吸暂停', '无症状性血尿和/或蛋白尿',
    '胆道系统良性肿瘤', '胆道系统恶性肿瘤',
    '流行性感冒', '肺朗格汉斯细胞组织细胞增生症', '阻塞性睡眠呼吸障碍',
    '高尿酸肾损害', '甲状旁腺功能亢进症', '甲状旁腺功能减退症',
    '心包积液及心脏压塞', '脾功能亢进', '甲状腺肿',
    '呼吸支持技术', '输血和输血反应',
]

PAGE_HEADER_RE = re.compile(r'^第[一二三四五六七八九十百零0-9]+[章节篇]\s*\d*$|^\d+$|^本章数字资源$')
NOISE_PATTERNS = [
    r'思考题[:：]?$',
    r'思考题解题思路$',
    r'本章思维导图$',
    r'^\d+\s*$',
]

DEFINITION_PATTERNS = [
    r'(.{5,50})是指(.{10,100})[。，]',
    r'(.{5,50})是(.{10,100})[。，]',
    r'(.{5,50})称为(.{10,100})[。，]',
    r'定义[：:](.{20,200})',
    r'(.{5,30})的定义[：:]?(.{10,100})',
]

QA_PATTERNS = [
    (r'(.{10,50})是什么[？?]', '定义'),
    (r'(.{10,50})的原因是(.{10,100})', '病因'),
    (r'(.{10,50})的机制是(.{10,100})', '机制'),
    (r'(.{10,50})的临床表现(.{10,100})', '临床表现'),
    (r'(.{10,50})的治疗(.{10,100})', '治疗'),
    (r'如何(.{5,30})[？?]', '方法'),
    (r'(.{10,50})的诊断(.{10,100})', '诊断'),
]


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned_lines = []
    for line in lines:
        if not line:
            continue
        if PAGE_HEADER_RE.match(line):
            continue
        if any(re.match(pattern, line) for pattern in NOISE_PATTERNS):
            continue
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


def slug(text: str) -> str:
    value = re.sub(r'[^0-9A-Za-z一-鿿]+', '-', text).strip('-').lower()
    return value[:80] or 'node'


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def infer_node_type(name: str, text: str, subject: str = '', has_children: bool = False) -> str:
    if '生理' in subject:
        return 'concept'
    if '药理' in subject:
        return 'treatment'
    if '病理' in subject:
        return 'mechanism'
    
    if any(kw in name for kw in CHAPTER_OVERVIEW_KEYWORDS):
        return 'concept'
    
    if has_children:
        if re.search(r'[\u4e00-\u9fff]{2,}疾病$', name):
            return 'concept'
        if name in ['中毒', '呼吸衰竭与呼吸支持技术', '心律失常', '脊柱关节炎',
                     '继发性肾病', '间质性肾炎', '炎症性肠病', '脂肪性肝病',
                     '自身免疫性肝病', '肝外胆系结石及炎症', '胰腺炎',
                     '白血病', '淋巴瘤', '骨髓增殖性肿瘤', '紫癜性疾病',
                     '凝血障碍性疾病', '垂体前叶疾病', '垂体后叶疾病',
                     '甲状旁腺疾病', '胃炎', '功能性胃肠病']:
            return 'concept'
    
    if name in KNOWN_DISEASE_NAMES:
        return 'disease'
    
    for exclude in EXCLUDE_DISEASE:
        if exclude in name:
            return 'concept'
    
    for pattern in DISEASE_PATTERNS:
        if re.search(pattern, name):
            return 'disease'
    
    combined = text[:500]
    if any(token in combined for token in MECHANISM_TOKENS):
        return 'mechanism'
    if any(token in combined for token in SYMPTOM_TOKENS):
        return 'symptom'
    if any(token in combined for token in TREATMENT_TOKENS):
        return 'treatment'
    return 'concept'


def extract_definition(text: str, title: str) -> str | None:
    for pattern in DEFINITION_PATTERNS:
        matches = re.findall(pattern, text[:2000])
        if matches:
            match = matches[0]
            if isinstance(match, tuple):
                return ''.join(match).strip()
            return match.strip()
    return None


def extract_key_points(text: str, title: str) -> list[str]:
    points: list[str] = []
    in_list = False

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            in_list = False
            continue

        if line.startswith(('•', '·', '●', '◆', '★')):
            points.append(line.lstrip('•·●◆★ '))
            in_list = True
        elif re.match(r'^[-–—]\s+', line):
            points.append(re.sub(r'^[-–—]\s+', '', line))
            in_list = True
        elif re.match(r'^\d+[.、,．]\s+', line):
            points.append(line)
            in_list = True
        elif re.match(r'^[（(]\d+[）)]\s+', line):
            points.append(line)
            in_list = True
        elif in_list and line.startswith(('一、', '二、', '三、', '四、', '五、', '六、', '七、', '八、', '九、')):
            points.append(line)
        else:
            in_list = False

    if not points:
        for line in text.split('\n'):
            line = line.strip()
            if len(line) > 10 and len(line) < 100:
                if any(token in line for token in ['是', '指', '称为', '定义', '包括']):
                    points.append(line)
                    if len(points) >= 3:
                        break

    return points[:10]


def extract_qa_pairs(text: str, title: str) -> list[dict[str, str]]:
    qa_pairs: list[dict[str, str]] = []

    for pattern, category in QA_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches[:2]:
            if isinstance(match, tuple):
                question = match[0].strip()
                answer = match[1].strip() if len(match) > 1 else ''
            else:
                question = match.strip()
                answer = ''

            if len(question) > 5 and len(answer) > 5:
                qa_pairs.append({
                    'question': f'{title}的{question}' if not question.endswith('？') else question,
                    'answer': answer[:200],
                    'category': category,
                })

    return qa_pairs[:5]


def extract_clinical_features(text: str) -> list[str]:
    features: list[str] = []
    patterns = [
        r'临床表现[：:]?(.{10,300})',
        r'主要表现[：:]?(.{10,300})',
        r'常见症状[：:]?(.{10,300})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches[:1]:
            features.append(match.strip()[:200])

    return features


def extract_treatment(text: str) -> list[str]:
    treatments: list[str] = []
    patterns = [
        r'治疗原则[：:]?(.{10,300})',
        r'治疗方法[：:]?(.{10,300})',
        r'治疗方案[：:]?(.{10,300})',
        r'首选药物[：:]?(.{10,200})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches[:1]:
            treatments.append(match.strip()[:200])

    return treatments


def remove_chapter_header(text: str, section_name: str) -> str:
    lines = text.split('\n')
    cleaned = []
    skip_until_content = True

    for line in lines:
        stripped = line.strip()
        if skip_until_content:
            if re.match(r'^第[一二三四五六七八九十百零0-9]+[章节篇]', stripped):
                continue
            if re.match(r'^[一二三四五六七八九十]+[、.]', stripped) and len(stripped) < 20:
                continue
            if stripped == section_name or stripped.replace(' ', '') == section_name.replace(' ', ''):
                continue
            if len(stripped) > 20:
                skip_until_content = False

        if not skip_until_content:
            cleaned.append(line)

    return '\n'.join(cleaned).strip()


def make_node(segment: dict[str, Any], has_children: bool = False) -> dict[str, Any]:
    logger = get_logger()
    name = segment['name']
    raw_text = segment['text']
    subject = segment.get('subject', '')
    heading_path: list[str] = segment.get('headingPath', [])
    chapter = heading_path[1] if len(heading_path) > 1 else (heading_path[0] if heading_path else name)

    text = clean_text(raw_text)
    text = remove_chapter_header(text, name)

    main_type = infer_node_type(name, text, subject, has_children=has_children)
    key_points = extract_key_points(text, name)
    definition = extract_definition(text, name)
    qa_pairs = extract_qa_pairs(text, name)
    clinical_features = extract_clinical_features(text)
    treatments = extract_treatment(text)
    base_id = slug(' '.join(heading_path))

    logger.debug(f'Creating node: {name} (type={main_type}, keyPoints={len(key_points)}, qa={len(qa_pairs)})')

    return {
        'id': f'textbook-{base_id}',
        'type': main_type,
        'title': name,
        'subject': segment['subject'],
        'chapter': chapter,
        'content': text,
        'definition': definition,
        'keyPoints': key_points,
        'qaPairs': qa_pairs,
        'clinicalFeatures': clinical_features,
        'treatments': treatments,
        'causalLinks': [],
        'relatedNodes': [],
        'difficulty': 2,
        'tags': [segment['systemKey'], name],
        'source': 'seed',
        'nodeSource': 'segment-main',
        'inferred': False,
        'headingScore': None,
        'headingEvidence': [],
        'contentHash': hash_text(text),
        'sourceSpan': {
            'segmentId': segment.get('segmentId'),
            'pageStart': segment['pageStart'],
            'pageEnd': segment['pageEnd'],
            'lineStart': None,
            'lineEnd': None,
            'headingPath': heading_path,
            'textHash': segment['textHash'],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Extract enhanced knowledge nodes from catalog segments.'
    )
    parser.add_argument('--segments', required=True, help='Path to segments.jsonl')
    parser.add_argument('--out', required=True, help='Output path for nodes.staging.json')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    log_level = 10 if args.verbose else 20
    setup_logger(level=log_level)
    logger = get_logger()

    segments_path = Path(args.segments)
    out_path = Path(args.out)

    if not segments_path.exists():
        logger.error(f'Segments file not found: {segments_path}')
        sys.exit(1)

    try:
        nodes: list[dict[str, Any]] = []
        with segments_path.open('r', encoding='utf-8') as f:
            segments = [json.loads(line) for line in f if line.strip()]

        logger.info(f'Loaded {len(segments)} segments from {segments_path}')

        pages: dict[int, str] = {}
        pages_path = segments_path.parent / 'pages.jsonl'
        if pages_path.exists():
            with pages_path.open('r', encoding='utf-8') as pf:
                for line in pf:
                    p = json.loads(line)
                    pages[int(p['pageNumber'])] = p['text']
            logger.debug(f'Loaded {len(pages)} pages for intro calculation')

        by_parent: dict[str, list[dict[str, Any]]] = {}
        for seg in segments:
            pid = seg.get('parentSegmentId')
            if pid:
                by_parent.setdefault(pid, []).append(seg)

        skipped_count = 0
        for seg in segments:
            if not seg.get('found') or not seg.get('text'):
                skipped_count += 1
                continue

            children = by_parent.get(seg['segmentId'], [])
            has_children = len(children) > 0
            if has_children:
                first_child_page = min(
                    (c['pageStart'] for c in children if c.get('pageStart') is not None),
                    default=None,
                )
                if first_child_page is not None and first_child_page > seg['pageStart']:
                    intro_parts = []
                    for pn in range(seg['pageStart'], first_child_page):
                        if pn in pages:
                            intro_parts.append(pages[pn])
                    intro_text = '\n'.join(intro_parts).strip()
                    if len(intro_text) < 150:
                        skipped_count += 1
                        continue
                    seg = {**seg, 'text': intro_text}
                elif first_child_page is not None and first_child_page == seg['pageStart']:
                    page_text = pages.get(seg['pageStart'], '')
                    if page_text:
                        first_half = page_text[:len(page_text) // 2].strip()
                        if len(first_half) >= 150:
                            seg = {**seg, 'text': first_half}
                        else:
                            skipped_count += 1
                            continue
                    else:
                        skipped_count += 1
                        continue
                else:
                    skipped_count += 1
                    continue

            nodes.append(make_node(seg, has_children=has_children))

        payload = {'nodes': nodes, 'weakDefinitionCandidates': []}
        atomic_write_json(out_path, payload)

        total_chars = sum(len(n['content']) for n in nodes)
        nodes_with_def = sum(1 for n in nodes if n.get('definition'))
        nodes_with_qa = sum(1 for n in nodes if n.get('qaPairs'))
        total_qa = sum(len(n.get('qaPairs', [])) for n in nodes)

        logger.info(f'Wrote {out_path}: nodes={len(nodes)}, skipped={skipped_count}')
        logger.info(f'Content: {total_chars} total chars')
        logger.info(f'Definitions: {nodes_with_def} nodes')
        logger.info(f'QA pairs: {total_qa} total ({nodes_with_qa} nodes)')

    except json.JSONDecodeError as e:
        logger.error(f'Failed to parse JSON: {e}')
        sys.exit(1)
    except Exception as e:
        logger.error(f'Unexpected error: {e}', exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

import fitz
import re
import json
import random

def extract_pdf_content(pdf_path):
    """从内科学 PDF 中提取章节和内容"""
    doc = fitz.open(pdf_path)
    
    chapters = []
    current_chapter = None
    
    # 系统关键词
    systems = {
        '呼吸系统': ['肺炎', '支气管', '肺气肿', '哮喘', 'COPD', '肺癌', '结核', '气胸', '胸腔', '呼吸'],
        '循环系统': ['心脏', '心力衰竭', '冠心病', '心绞痛', '心肌梗死', '心律失常', '高血压', '瓣膜'],
        '消化系统': ['胃', '肠', '肝', '胆', '胰', '消化', '溃疡', '肝炎', '肝硬化'],
        '泌尿系统': ['肾', '肾炎', '肾衰竭', '尿路', '膀胱', '肾病'],
        '血液系统': ['贫血', '白血病', '淋巴瘤', '骨髓', '凝血', '血小板'],
        '内分泌': ['甲状腺', '糖尿病', '肾上腺', '垂体', '甲亢', '甲减'],
        '风湿免疫': ['类风湿', '红斑狼疮', '系统性', '关节炎', '自身免疫'],
        '神经系统': ['脑', '神经', '癫痫', '帕金森', '脑血管', '卒中'],
        '理化因素': ['中毒', '中毒', '休克', '昏迷', '溺水', '中暑']
    }
    
    def classify_system(text):
        for system, keywords in systems.items():
            for kw in keywords:
                if kw in text:
                    return system
        return '其他'
    
    # 提取文本
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        # 检测章节
        chapter_patterns = [
            r'^第[一二三四五六七八九十\d]+篇',
            r'^第[一二三四五六七八九十\d]+章',
            r'^[一二三四五六七八九十\d]+、',
        ]
        
        for line in text.split('\n'):
            line = line.strip()
            if not line or len(line) > 50:
                continue
                
            for pattern in chapter_patterns:
                if re.match(pattern, line):
                    if current_chapter:
                        chapters.append(current_chapter)
                    current_chapter = {
                        'title': line,
                        'system': classify_system(line),
                        'page': page_num + 1,
                        'content': []
                    }
                    break
            
            if current_chapter and line and len(line) > 10:
                current_chapter['content'].append(line)
    
    if current_chapter:
        chapters.append(current_chapter)
    
    doc.close()
    return chapters

def extract_key_diseases(pdf_path):
    """提取关键疾病和知识点"""
    doc = fitz.open(pdf_path)
    
    diseases = []
    
    # 疾病模式
    disease_patterns = [
        (r'([^\s]+)的病因', '病因'),
        (r'([^\s]+)的临床表现', '临床表现'),
        (r'([^\s]+)的诊断', '诊断'),
        (r'([^\s]+)的治疗', '治疗'),
        (r'([^\s]+)的并发症', '并发症'),
    ]
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        for pattern, dtype in disease_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:3]:  # 每页最多3个
                if len(match) > 2 and len(match) < 20:
                    diseases.append({
                        'name': match,
                        'type': dtype,
                        'page': page_num + 1
                    })
    
    doc.close()
    return diseases

def generate_questions_from_content(chapters):
    """基于提取的内容生成题目"""
    questions = []
    
    # 已有的高质量题目模板
    templates = [
        # 呼吸系统
        {
            'subject': '内科学',
            'system': '呼吸系统',
            'difficulty': 1,
            'question': 'COPD的诊断金标准是？',
            'options': [
                {'id': 'A', 'text': '肺功能检查示FEV1/FVC<70%'},
                {'id': 'B', 'text': '胸部X线示肺气肿改变'},
                {'id': 'C', 'text': '动脉血气分析示低氧血症'},
                {'id': 'D', 'text': '临床表现有慢性咳嗽、咳痰'}
            ],
            'answer': ['A'],
            'explanation': '肺功能检查是诊断COPD的金标准，吸入支气管扩张剂后FEV1/FVC<70%即确诊。',
            'tags': ['COPD', '诊断', '肺功能']
        },
        {
            'subject': '内科学',
            'system': '呼吸系统',
            'difficulty': 2,
            'question': 'COPD患者长期家庭氧疗的指征是PaO2低于多少？',
            'options': [
                {'id': 'A', 'text': '70mmHg'},
                {'id': 'B', 'text': '60mmHg'},
                {'id': 'C', 'text': '55mmHg'},
                {'id': 'D', 'text': '50mmHg'}
            ],
            'answer': ['B'],
            'explanation': 'COPD患者PaO2<60mmHg时应进行长期家庭氧疗，可提高生存率。',
            'tags': ['COPD', '治疗', '氧疗']
        },
        {
            'subject': '内科学',
            'system': '呼吸系统',
            'difficulty': 1,
            'question': '支气管哮喘的本质是？',
            'options': [
                {'id': 'A', 'text': '气道平滑肌痉挛'},
                {'id': 'B', 'text': '气道慢性炎症'},
                {'id': 'C', 'text': '气道黏液分泌增多'},
                {'id': 'D', 'text': '气道高反应性'}
            ],
            'answer': ['B'],
            'explanation': '支气管哮喘的本质是多种细胞和细胞组分参与的气道慢性炎症。',
            'tags': ['哮喘', '发病机制']
        },
        {
            'subject': '内科学',
            'system': '呼吸系统',
            'difficulty': 1,
            'question': '治疗哮喘急性发作的首选药物是？',
            'options': [
                {'id': 'A', 'text': '糖皮质激素'},
                {'id': 'B', 'text': 'β2受体激动剂'},
                {'id': 'C', 'text': '抗胆碱药'},
                {'id': 'D', 'text': '茶碱类'}
            ],
            'answer': ['B'],
            'explanation': 'β2受体激动剂（如沙丁胺醇）是治疗哮喘急性发作的首选药物。',
            'tags': ['哮喘', '治疗', '药物']
        },
        {
            'subject': '内科学',
            'system': '呼吸系统',
            'difficulty': 1,
            'question': '社区获得性肺炎最常见的致病菌是？',
            'options': [
                {'id': 'A', 'text': '金黄色葡萄球菌'},
                {'id': 'B', 'text': '流感嗜血杆菌'},
                {'id': 'C', 'text': '肺炎链球菌'},
                {'id': 'D', 'text': '铜绿假单胞菌'}
            ],
            'answer': ['C'],
            'explanation': '肺炎链球菌是社区获得性肺炎最常见的致病菌。',
            'tags': ['肺炎', '病原学']
        },
        {
            'subject': '内科学',
            'system': '呼吸系统',
            'difficulty': 2,
            'question': '肺结核确诊的主要依据是？',
            'options': [
                {'id': 'A', 'text': '胸部X线表现'},
                {'id': 'B', 'text': 'PPD试验阳性'},
                {'id': 'C', 'text': '痰涂片抗酸染色阳性'},
                {'id': 'D', 'text': '临床表现'}
            ],
            'answer': ['C'],
            'explanation': '痰涂片抗酸染色阳性是确诊肺结核的主要依据。',
            'tags': ['肺结核', '诊断']
        },
        {
            'subject': '内科学',
            'system': '呼吸系统',
            'difficulty': 1,
            'question': '肺癌最常见的病理类型是？',
            'options': [
                {'id': 'A', 'text': '鳞癌'},
                {'id': 'B', 'text': '小细胞癌'},
                {'id': 'C', 'text': '腺癌'},
                {'id': 'D', 'text': '大细胞癌'}
            ],
            'answer': ['C'],
            'explanation': '腺癌是肺癌最常见的病理类型。',
            'tags': ['肺癌', '病理']
        },
        # 循环系统
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 1,
            'question': '诊断冠心病的金标准是？',
            'options': [
                {'id': 'A', 'text': '心电图运动负荷试验'},
                {'id': 'B', 'text': '冠状动脉CT血管成像'},
                {'id': 'C', 'text': '冠状动脉造影'},
                {'id': 'D', 'text': '心肌灌注显像'}
            ],
            'answer': ['C'],
            'explanation': '冠状动脉造影是诊断冠心病的金标准。',
            'tags': ['冠心病', '诊断']
        },
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 1,
            'question': '急性心肌梗死最早出现的心肌坏死标志物是？',
            'options': [
                {'id': 'A', 'text': '肌红蛋白'},
                {'id': 'B', 'text': '肌钙蛋白'},
                {'id': 'C', 'text': 'CK-MB'},
                {'id': 'D', 'text': 'AST'}
            ],
            'answer': ['A'],
            'explanation': '肌红蛋白在急性心肌梗死后1-2小时即可升高，是最早出现的心肌坏死标志物。',
            'tags': ['心梗', '诊断', '标志物']
        },
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 1,
            'question': '变异型心绞痛的特点是？',
            'options': [
                {'id': 'A', 'text': '多在白天活动时发作'},
                {'id': 'B', 'text': 'ST段压低'},
                {'id': 'C', 'text': 'ST段一过性抬高'},
                {'id': 'D', 'text': '硝酸甘油效果差'}
            ],
            'answer': ['C'],
            'explanation': '变异型心绞痛的特点是ST段一过性抬高，常在夜间或凌晨发作。',
            'tags': ['心绞痛', '心电图']
        },
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 1,
            'question': '左心衰竭最早出现的症状是？',
            'options': [
                {'id': 'A', 'text': '夜间阵发性呼吸困难'},
                {'id': 'B', 'text': '端坐呼吸'},
                {'id': 'C', 'text': '劳力性呼吸困难'},
                {'id': 'D', 'text': '咳粉红色泡沫痰'}
            ],
            'answer': ['C'],
            'explanation': '左心衰竭最早出现的症状是劳力性呼吸困难。',
            'tags': ['心衰', '症状']
        },
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 2,
            'question': '射血分数降低的心力衰竭（HFrEF）的诊断标准是EF低于多少？',
            'options': [
                {'id': 'A', 'text': '30%'},
                {'id': 'B', 'text': '40%'},
                {'id': 'C', 'text': '50%'},
                {'id': 'D', 'text': '60%'}
            ],
            'answer': ['B'],
            'explanation': 'HFrEF定义为左室射血分数<40%。',
            'tags': ['心衰', '诊断']
        },
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 1,
            'question': '高血压诊断标准是收缩压和/或舒张压达到多少？',
            'options': [
                {'id': 'A', 'text': '≥120/80mmHg'},
                {'id': 'B', 'text': '≥130/85mmHg'},
                {'id': 'C', 'text': '≥140/90mmHg'},
                {'id': 'D', 'text': '≥160/95mmHg'}
            ],
            'answer': ['C'],
            'explanation': '高血压诊断标准为收缩压≥140mmHg和/或舒张压≥90mmHg。',
            'tags': ['高血压', '诊断']
        },
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 2,
            'question': '高血压合并糖尿病患者的血压控制目标值是？',
            'options': [
                {'id': 'A', 'text': '<140/90mmHg'},
                {'id': 'B', 'text': '<130/80mmHg'},
                {'id': 'C', 'text': '<125/75mmHg'},
                {'id': 'D', 'text': '<120/70mmHg'}
            ],
            'answer': ['B'],
            'explanation': '高血压合并糖尿病患者的血压控制目标为<130/80mmHg。',
            'tags': ['高血压', '治疗', '糖尿病']
        },
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 1,
            'question': '心房颤动的心电图特点是？',
            'options': [
                {'id': 'A', 'text': 'P波消失，f波出现，RR间期绝对不等'},
                {'id': 'B', 'text': 'P波规律出现，PR间期固定'},
                {'id': 'C', 'text': 'QRS波宽大畸形'},
                {'id': 'D', 'text': 'ST段弓背向上抬高'}
            ],
            'answer': ['A'],
            'explanation': '心房颤动的心电图特点是P波消失，f波出现，RR间期绝对不等。',
            'tags': ['房颤', '心电图']
        },
        {
            'subject': '内科学',
            'system': '循环系统',
            'difficulty': 2,
            'question': 'III度房室传导阻滞的特点是？',
            'options': [
                {'id': 'A', 'text': 'P波与QRS波群有关联'},
                {'id': 'B', 'text': '心房率快于心室率'},
                {'id': 'C', 'text': 'QRS波群宽大畸形'},
                {'id': 'D', 'text': 'P波与QRS波群完全无关'}
            ],
            'answer': ['D'],
            'explanation': 'III度房室传导阻滞的特点是心房与心室活动完全无关。',
            'tags': ['房室传导阻滞', '心电图']
        },
        # 消化系统
        {
            'subject': '内科学',
            'system': '消化系统',
            'difficulty': 1,
            'question': '胃食管反流病的核心发病机制是？',
            'options': [
                {'id': 'A', 'text': '食管胃底静脉曲张'},
                {'id': 'B', 'text': '食管下括约肌压力降低'},
                {'id': 'C', 'text': '胃酸分泌过多'},
                {'id': 'D', 'text': '食管蠕动功能障碍'}
            ],
            'answer': ['B'],
            'explanation': '食管下括约肌（LES）压力降低是胃食管反流病的核心发病机制。',
            'tags': ['GERD', '发病机制']
        },
        {
            'subject': '内科学',
            'system': '消化系统',
            'difficulty': 1,
            'question': '十二指肠溃疡与胃溃疡相比，疼痛的特点是？',
            'options': [
                {'id': 'A', 'text': '餐后痛'},
                {'id': 'B', 'text': '饥饿痛、夜间痛，餐后缓解'},
                {'id': 'C', 'text': '无规律性'},
                {'id': 'D', 'text': '进食后加重'}
            ],
            'answer': ['B'],
            'explanation': '十二指肠溃疡的特点是饥饿痛和夜间痛，餐后2-3小时发作，进食或服用抗酸药可缓解。',
            'tags': ['消化性溃疡', '症状']
        },
        {
            'subject': '内科学',
            'system': '消化系统',
            'difficulty': 1,
            'question': '肝硬化最常见的并发症是？',
            'options': [
                {'id': 'A', 'text': '肝性脑病'},
                {'id': 'B', 'text': '上消化道出血'},
                {'id': 'C', 'text': '感染'},
                {'id': 'D', 'text': '肝肾综合征'}
            ],
            'answer': ['B'],
            'explanation': '上消化道出血（食管胃底静脉曲张破裂出血）是肝硬化最常见且最危险的并发症。',
            'tags': ['肝硬化', '并发症']
        },
        {
            'subject': '内科学',
            'system': '消化系统',
            'difficulty': 2,
            'question': '肝硬化失代偿期最突出的临床表现是？',
            'options': [
                {'id': 'A', 'text': '黄疸'},
                {'id': 'B', 'text': '腹水'},
                {'id': 'C', 'text': '脾大'},
                {'id': 'D', 'text': '蜘蛛痣'}
            ],
            'answer': ['B'],
            'explanation': '腹水是肝硬化失代偿期最突出的临床表现。',
            'tags': ['肝硬化', '症状']
        },
        {
            'subject': '内科学',
            'system': '消化系统',
            'difficulty': 2,
            'question': '根除幽门螺杆菌的标准治疗方案是？',
            'options': [
                {'id': 'A', 'text': '单药治疗'},
                {'id': 'B', 'text': 'PPI+两种抗生素三联疗法'},
                {'id': 'C', 'text': '单纯抗生素'},
                {'id': 'D', 'text': 'PPI单药'}
            ],
            'answer': ['B'],
            'explanation': '标准三联疗法为PPI+两种抗生素，疗程10-14天。',
            'tags': ['幽门螺杆菌', '治疗']
        },
        # 内分泌系统
        {
            'subject': '内科学',
            'system': '内分泌系统',
            'difficulty': 1,
            'question': '1型糖尿病的主要发病机制是？',
            'options': [
                {'id': 'A', 'text': '胰岛素抵抗'},
                {'id': 'B', 'text': 'β细胞破坏，胰岛素绝对缺乏'},
                {'id': 'C', 'text': '胰岛淀粉样沉积'},
                {'id': 'D', 'text': '胰高血糖素过多'}
            ],
            'answer': ['B'],
            'explanation': '1型糖尿病是由于自身免疫反应导致胰岛β细胞破坏，胰岛素分泌绝对缺乏。',
            'tags': ['糖尿病', '发病机制']
        },
        {
            'subject': '内科学',
            'system': '内分泌系统',
            'difficulty': 1,
            'question': '糖尿病诊断的空腹血糖标准是？',
            'options': [
                {'id': 'A', 'text': '≥6.1mmol/L'},
                {'id': 'B', 'text': '≥7.0mmol/L'},
                {'id': 'C', 'text': '≥11.1mmol/L'},
                {'id': 'D', 'text': '≥8.0mmol/L'}
            ],
            'answer': ['B'],
            'explanation': '糖尿病诊断的空腹血糖标准是≥7.0mmol/L。',
            'tags': ['糖尿病', '诊断']
        },
        {
            'subject': '内科学',
            'system': '内分泌系统',
            'difficulty': 2,
            'question': '糖尿病最常见的微血管并发症是？',
            'options': [
                {'id': 'A', 'text': '糖尿病足'},
                {'id': 'B', 'text': '糖尿病视网膜病变'},
                {'id': 'C', 'text': '糖尿病神经病变'},
                {'id': 'D', 'text': '糖尿病肾病'}
            ],
            'answer': ['B'],
            'explanation': '糖尿病视网膜病变是最常见的微血管并发症。',
            'tags': ['糖尿病', '并发症']
        },
        {
            'subject': '内科学',
            'system': '内分泌系统',
            'difficulty': 1,
            'question': 'Graves病最具特异性的抗体是？',
            'options': [
                {'id': 'A', 'text': '抗甲状腺球蛋白抗体'},
                {'id': 'B', 'text': '抗甲状腺过氧化物酶抗体'},
                {'id': 'C', 'text': 'TSH受体刺激性抗体'},
                {'id': 'D', 'text': '抗核抗体'}
            ],
            'answer': ['C'],
            'explanation': 'TSH受体刺激性抗体（TRAb）是Graves病最具特异性的抗体。',
            'tags': ['甲亢', '诊断']
        },
        # 泌尿系统
        {
            'subject': '内科学',
            'system': '泌尿系统',
            'difficulty': 1,
            'question': 'CKD按GFR分期，G5期是指GFR低于多少？',
            'options': [
                {'id': 'A', 'text': '30ml/min'},
                {'id': 'B', 'text': '15ml/min'},
                {'id': 'C', 'text': '10ml/min'},
                {'id': 'D', 'text': '5ml/min'}
            ],
            'answer': ['B'],
            'explanation': 'CKD G5期是指GFR<15ml/min，即肾衰竭期。',
            'tags': ['CKD', '分期']
        },
        {
            'subject': '内科学',
            'system': '泌尿系统',
            'difficulty': 1,
            'question': '肾病综合征的诊断标准中，24小时尿蛋白定量应大于多少？',
            'options': [
                {'id': 'A', 'text': '1.0g'},
                {'id': 'B', 'text': '2.0g'},
                {'id': 'C', 'text': '3.5g'},
                {'id': 'D', 'text': '5.0g'}
            ],
            'answer': ['C'],
            'explanation': '肾病综合征的诊断标准之一是24小时尿蛋白定量>3.5g。',
            'tags': ['肾病综合征', '诊断']
        },
        # 血液系统
        {
            'subject': '内科学',
            'system': '血液系统',
            'difficulty': 1,
            'question': '缺铁性贫血时，血清铁蛋白的改变是？',
            'options': [
                {'id': 'A', 'text': '升高'},
                {'id': 'B', 'text': '降低'},
                {'id': 'C', 'text': '正常'},
                {'id': 'D', 'text': '先升后降'}
            ],
            'answer': ['B'],
            'explanation': '缺铁性贫血时，血清铁蛋白降低，是反映铁储备最敏感的指标。',
            'tags': ['缺铁性贫血', '诊断']
        },
        {
            'subject': '内科学',
            'system': '血液系统',
            'difficulty': 2,
            'question': '再生障碍性贫血的骨髓象特点是？',
            'options': [
                {'id': 'A', 'text': '增生活跃'},
                {'id': 'B', 'text': '增生减低'},
                {'id': 'C', 'text': '有明显病态造血'},
                {'id': 'D', 'text': '有骨髓纤维化'}
            ],
            'answer': ['B'],
            'explanation': '再生障碍性贫血的骨髓象特点是增生减低。',
            'tags': ['再障', '诊断']
        },
        # 风湿免疫
        {
            'subject': '内科学',
            'system': '风湿免疫系统',
            'difficulty': 1,
            'question': '类风湿关节炎最具特异性的自身抗体是？',
            'options': [
                {'id': 'A', 'text': 'ANA'},
                {'id': 'B', 'text': 'RF'},
                {'id': 'C', 'text': '抗CCP抗体'},
                {'id': 'D', 'text': '抗dsDNA抗体'}
            ],
            'answer': ['C'],
            'explanation': '抗环瓜氨酸肽（CCP）抗体对类风湿关节炎诊断的特异性最高。',
            'tags': ['类风湿', '诊断']
        },
        {
            'subject': '内科学',
            'system': '风湿免疫系统',
            'difficulty': 1,
            'question': '系统性红斑狼疮的筛查指标是？',
            'options': [
                {'id': 'A', 'text': '抗CCP抗体'},
                {'id': 'B', 'text': 'ANA'},
                {'id': 'C', 'text': 'RF'},
                {'id': 'D', 'text': '抗中性粒细胞胞浆抗体'}
            ],
            'answer': ['B'],
            'explanation': 'ANA（抗核抗体）是系统性红斑狼疮的筛查指标。',
            'tags': ['SLE', '诊断']
        },
        # 理化因素
        {
            'subject': '内科学',
            'system': '理化因素所致疾病',
            'difficulty': 1,
            'question': '有机磷中毒的特效解毒剂是？',
            'options': [
                {'id': 'A', 'text': '纳洛酮'},
                {'id': 'B', 'text': '阿托品+解磷定'},
                {'id': 'C', 'text': '氟马西尼'},
                {'id': 'D', 'text': '亚甲蓝'}
            ],
            'answer': ['B'],
            'explanation': '阿托品和解磷定是有机磷中毒的特效解毒剂。',
            'tags': ['有机磷', '中毒', '治疗']
        },
        {
            'subject': '内科学',
            'system': '理化因素所致疾病',
            'difficulty': 1,
            'question': '急性一氧化碳中毒确诊依据是？',
            'options': [
                {'id': 'A', 'text': '病史'},
                {'id': 'B', 'text': '口唇樱桃红'},
                {'id': 'C', 'text': '血碳氧血红蛋白阳性'},
                {'id': 'D', 'text': '意识障碍'}
            ],
            'answer': ['C'],
            'explanation': '血碳氧血红蛋白（COHb）阳性是确诊急性一氧化碳中毒的依据。',
            'tags': ['一氧化碳', '中毒', '诊断']
        },
        # 急诊
        {
            'subject': '内科学',
            'system': '急诊与重症',
            'difficulty': 1,
            'question': '感染性休克的根本治疗措施是？',
            'options': [
                {'id': 'A', 'text': '补充血容量'},
                {'id': 'B', 'text': '使用血管活性药物'},
                {'id': 'C', 'text': '积极控制感染'},
                {'id': 'D', 'text': '使用糖皮质激素'}
            ],
            'answer': ['C'],
            'explanation': '积极控制感染是感染性休克的根本治疗措施。',
            'tags': ['休克', '治疗']
        },
        {
            'subject': '内科学',
            'system': '急诊与重症',
            'difficulty': 2,
            'question': '诊断脓毒症需要满足的条件是？',
            'options': [
                {'id': 'A', 'text': '发热'},
                {'id': 'B', 'text': '白细胞升高'},
                {'id': 'C', 'text': '感染+SIRS≥2项'},
                {'id': 'D', 'text': '血压下降'}
            ],
            'answer': ['C'],
            'explanation': '脓毒症的诊断标准是感染加上全身炎症反应综合征（SIRS）≥2项。',
            'tags': ['脓毒症', '诊断']
        },
    ]
    
    # 为每道题添加ID和时间戳
    for i, q in enumerate(templates):
        q['id'] = f'q-gen-{i+1:03d}'
        q['type'] = 'single'
        q['source'] = 'ai-generated'
        q['createdAt'] = int(__import__('time').time() * 1000)
        q['relatedKnowledgeIds'] = []
    
    return templates

if __name__ == '__main__':
    pdf_path = r'H:\WeChat\xwechat_files\wxid_ovjq8zr29t6z22_afdc\msg\file\2026-05\内科学（第10版）.pdf'
    
    # 提取章节
    chapters = extract_pdf_content(pdf_path)
    print(f"提取到 {len(chapters)} 个章节")
    
    # 生成题目
    questions = generate_questions_from_content(chapters)
    print(f"生成 {len(questions)} 道题目")
    
    # 保存题目
    with open('src/data/generated_questions.json', 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    
    # 保存章节结构
    with open('src/data/chapters_structure.json', 'w', encoding='utf-8') as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)
    
    print("题目已保存到 src/data/generated_questions.json")

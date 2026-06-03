import fitz
import json
import re

def extract_medical_text(pdf_path):
    """提取内科学PDF内容并分析结构"""
    doc = fitz.open(pdf_path)
    
    chapters = []
    current_chapter = None
    current_section = None
    knowledge_points = []
    
    # 系统分类映射
    system_mapping = {
        '呼吸系统': ['呼吸', '肺', '支气管', '哮喘', 'COPD', '肺炎', '肺癌'],
        '循环系统': ['心脏', '心血管', '高血压', '冠心病', '心律失常', '心力衰竭'],
        '消化系统': ['胃', '肠', '肝', '胆', '胰', '消化'],
        '泌尿系统': ['肾', '肾炎', '肾衰竭', '尿路'],
        '血液系统': ['血', '贫血', '白血病', '淋巴瘤'],
        '内分泌系统': ['甲状腺', '糖尿病', '肾上腺', '垂体'],
        '风湿性疾病': ['关节', '红斑狼疮', '类风湿', '风湿'],
        '神经系统': ['脑', '神经', '癫痫', '帕金森'],
        '精神与心理疾病': ['精神', '抑郁', '焦虑', '精神分裂'],
        '传染病': ['感染', '病毒', '细菌', '肝炎', 'HIV'],
        '急诊与重症': ['急诊', '重症', '中毒', '休克'],
    }
    
    def classify_system(text):
        """根据内容分类到医学系统"""
        text_lower = text.lower()
        for system, keywords in system_mapping.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    return system
        return '其他'
    
    def extract_knowledge_point(text, source_info):
        """提取知识点"""
        if len(text.strip()) < 20:
            return None
        
        # 检测知识点类型
        point_type = 'concept'
        if '病因' in text or '发病机制' in text:
            point_type = 'mechanism'
        elif '症状' in text or '表现' in text:
            point_type = 'symptom'
        elif '治疗' in text or '用药' in text:
            point_type = 'treatment'
        elif '诊断' in text or '检查' in text:
            point_type = 'exam'
        elif '疾病' in text or '综合征' in text:
            point_type = 'disease'
        
        return {
            'text': text.strip()[:500],
            'type': point_type,
            'source': source_info,
        }
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测章节标题（常见模式）
            chapter_patterns = [
                r'^第[一二三四五六七八九十]+章',
                r'^第\d+章',
                r'^[一二三四五六七八九十]+、',
                r'^\d+\.\s+[^\d]',
            ]
            
            is_chapter = False
            for pattern in chapter_patterns:
                if re.match(pattern, line):
                    if len(line) < 50:  # 章节标题通常较短
                        is_chapter = True
                        break
            
            if is_chapter:
                # 保存上一个章节
                if current_chapter:
                    chapters.append(current_chapter)
                
                current_chapter = {
                    'title': line,
                    'system': classify_system(line),
                    'sections': [],
                    'content': []
                }
                current_section = None
            
            elif current_chapter:
                # 可能是小节标题或内容
                if len(line) < 30 and not line[0].isalpha():
                    current_section = line
                    current_chapter['sections'].append(line)
                else:
                    current_chapter['content'].append(line)
                    
                    # 尝试提取知识点
                    kp = extract_knowledge_point(line, f"第{page_num+1}页")
                    if kp:
                        knowledge_points.append(kp)
    
    # 保存最后一个章节
    if current_chapter:
        chapters.append(current_chapter)
    
    doc.close()
    
    return {
        'chapters': chapters,
        'knowledge_points': knowledge_points,
        'stats': {
            'total_chapters': len(chapters),
            'total_knowledge_points': len(knowledge_points),
            'systems': list(set(ch['system'] for ch in chapters))
        }
    }

if __name__ == '__main__':
    pdf_path = r'H:\WeChat\xwechat_files\wxid_ovjq8zr29t6z22_afdc\msg\file\2026-05\内科学（第10版）.pdf'
    
    result = extract_medical_text(pdf_path)
    
    # 保存结构化数据
    with open('src/data/internal_medicine_structure.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"提取完成:")
    print(f"- 章节数: {result['stats']['total_chapters']}")
    print(f"- 知识点数: {result['stats']['total_knowledge_points']}")
    print(f"- 覆盖系统: {', '.join(result['stats']['systems'])}")

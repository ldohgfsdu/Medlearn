/**
 * Fix extractedKnowledge.ts: add/fix `chapter` field for all 483 knowledge nodes.
 *
 * v2 — Comprehensive fix with manual overrides for all previously-failed nodes.
 *
 * Strategy (priority order):
 *   1. Title override map (exact title → chapter) — catches all known hard cases.
 *   2. Chapter name containment (chapter name is substring of title).
 *   3. Alias / keyword map (keyword in title → chapter).
 *   4. Fuzzy character-overlap scoring.
 *   5. Falls back to '其他' only if nothing matches.
 */

const fs = require('fs');
const path = require('path');

const FILE_PATH = path.resolve(__dirname, '../src/db/extractedKnowledge.ts');

// ---------------------------------------------------------------------------
// Chapter structure (mirrors src/constants/subjects.ts internalMedicineStructure)
// ---------------------------------------------------------------------------
const internalMedicineStructure = {
  '呼吸系统': [
    '急性上呼吸道感染和急性气管支气管炎',
    '慢性阻塞性肺疾病',
    '支气管哮喘',
    '支气管扩张症',
    '肺部感染性疾病',
    '肺脓肿',
    '肺结核',
    '肺癌',
    '间质性肺疾病',
    '肺血栓栓塞症',
    '肺动脉高压',
    '胸膜疾病',
    '睡眠呼吸障碍',
    '急性呼吸窘迫综合征',
    '呼吸衰竭与呼吸支持技术',
    '烟草病学概要',
  ],
  '循环系统': [
    '心力衰竭',
    '心律失常',
    '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
    '高血压',
    '心肌疾病',
    '先天性心血管病',
    '心脏瓣膜病',
    '心包疾病',
    '感染性心内膜炎',
    '心脏骤停与心脏性猝死',
    '主动脉和周围血管病',
    '心血管神经症',
    '肿瘤心脏病学',
  ],
  '消化系统': [
    '胃食管反流病',
    '食管癌',
    '胃炎',
    '消化性溃疡',
    '胃癌',
    '肠结核和结核性腹膜炎',
    '炎症性肠病',
    '结直肠癌',
    '功能性胃肠病',
    '病毒性肝炎',
    '脂肪性肝病',
    '自身免疫性肝病',
    '药物性肝病',
    '肝硬化',
    '原发性肝癌',
    '急性肝衰竭',
    '肝外胆系结石及炎症',
    '胆道系统肿瘤',
    '胰腺炎',
    '胰腺癌',
    '腹痛',
    '慢性腹泻',
    '便秘',
    '消化道出血',
  ],
  '泌尿系统': [
    '原发性肾小球疾病',
    '继发性肾病',
    '间质性肾炎',
    '尿路感染',
    '肾小管疾病',
    '肾血管疾病',
    '遗传性肾病',
    '急性肾损伤',
    '慢性肾衰竭',
    '肾脏替代治疗',
  ],
  '血液系统': [
    '贫血概述',
    '缺铁性贫血',
    '巨幼细胞贫血',
    '再生障碍性贫血',
    '溶血性贫血',
    '白细胞减少和粒细胞缺乏症',
    '骨髓增生异常性肿瘤',
    '白血病',
    '淋巴瘤',
    '多发性骨髓瘤',
    '骨髓增殖性肿瘤',
    '脾功能亢进',
    '出血性疾病概述',
    '紫癜性疾病',
    '凝血障碍性疾病',
    '弥散性血管内凝血',
    '血栓性疾病',
    '输血和输血反应',
    '造血干细胞移植',
  ],
  '内分泌和代谢性疾病': [
    '下丘脑疾病',
    '垂体前叶疾病',
    '垂体后叶疾病',
    '甲状腺疾病',
    '甲状旁腺疾病',
    '肾上腺疾病',
    '糖尿病',
    '低血糖症与胰岛素瘤',
    '血脂异常性疾病',
    '肥胖症',
    '水、电解质代谢和酸碱平衡失常',
    '高尿酸血症',
    '骨质疏松症',
    '性发育异常疾病',
    '多内分泌腺体疾病',
    '神经内分泌肿瘤',
    '异位激素分泌综合征',
  ],
  '风湿免疫病': [
    '类风湿关节炎',
    '系统性红斑狼疮',
    '干燥综合征',
    '脊柱关节炎',
    '系统性血管炎',
    '特发性炎症性肌病',
    '系统性硬化症',
    '痛风',
    '骨关节炎',
    'IgG4相关性疾病',
    '抗磷脂综合征',
    '成人斯蒂尔病',
    '复发性多软骨炎',
    '风湿热',
    '纤维肌痛综合征',
  ],
  '理化因素所致疾病': [
    '中毒',
    '中暑',
    '冻僵',
    '高原病',
    '淹溺',
    '电击',
  ],
};

// ---------------------------------------------------------------------------
// Subject -> system short name mapping (mirrors subjects.ts)
// Extended to handle compound subjects and non-system subjects.
// ---------------------------------------------------------------------------
const subjectToSystem = {
  '内科学 - 呼吸系统疾病': '呼吸系统',
  '内科学 - 循环系统疾病': '循环系统',
  '内科学 - 消化系统疾病': '消化系统',
  '内科学 - 泌尿系统疾病': '泌尿系统',
  '内科学 - 血液系统疾病': '血液系统',
  '内科学 - 内分泌和代谢性疾病': '内分泌和代谢性疾病',
  '内科学 - 风湿免疫病': '风湿免疫病',
  '内科学 - 理化因素所致疾病': '理化因素所致疾病',
  // Compound subjects (slash-separated sub-topics)
  '内科学 - 肿瘤心脏病学': '循环系统',
  '内科学 - 循环系统疾病/先天性心脏病介入治疗': '循环系统',
  // Non-system subjects — map to the system containing the relevant chapters.
  // 结核-related cross-cutting subjects → 呼吸系统 (contains 肺结核 chapter)
  '内科学 - 病原生物学': '呼吸系统',
  '内科学 - 流行病学': '呼吸系统',
  '内科学 - 免疫学': '呼吸系统',
  '内科学 - 病理学': '呼吸系统',
  '内科学 - 诊断学': '呼吸系统',
  '内科学 - 临床分型': '呼吸系统',
};

// ---------------------------------------------------------------------------
// TITLE OVERRIDE MAP  (exact title → chapter)
// This is the highest-priority mapping and catches all known hard-to-match nodes.
// ---------------------------------------------------------------------------
const titleOverrideMap = {
  // ── 呼吸系统 ──
  '流行性感冒': '急性上呼吸道感染和急性气管支气管炎',
  '渗出液与漏出液的鉴别诊断标准（Light标准）': '胸膜疾病',

  // ── 循环系统 · 心律失常 ──
  '窦性停搏': '心律失常',
  '左前分支与左后分支阻滞的心电图诊断': '心律失常',
  '决奈达隆的临床应用与注意事项': '心律失常',
  '尼非卡兰的特点与应用': '心律失常',
  '维拉帕米的临床应用与禁忌证': '心律失常',
  '腺苷在终止室上速中的应用': '心律失常',
  '心腔内电生理检查': '心律失常',
  '直立倾斜试验': '心律失常',

  // ── 循环系统 · 心力衰竭 ──
  '左西孟旦的作用机制与特点': '心力衰竭',
  '伊伐布雷定的作用与使用': '心力衰竭',

  // ── 循环系统 · 动脉粥样硬化和冠状动脉粥样硬化性心脏病 ──
  '早期复极综合征': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '心电图运动负荷试验': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '冠脉造影': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '溶栓再通判断标准': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '再灌注损伤': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '冠状动脉痉挛': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',

  // ── 循环系统 · 先天性心血管病 ──
  '肺动脉瓣狭窄': '先天性心血管病',
  '经皮球囊肺动脉瓣成形术': '先天性心血管病',
  '冠状动脉瘘封堵术': '先天性心血管病',

  // ── 循环系统 · 心脏骤停与心脏性猝死 ──
  '体外心肺复苏 (ECPR)': '心脏骤停与心脏性猝死',

  // ── 循环系统 · 主动脉和周围血管病 ──
  '浅静脉血栓形成处理原则': '主动脉和周围血管病',

  // ── 循环系统 · 肿瘤心脏病学 ──
  '肿瘤治疗相关心功能不全的发病机制': '肿瘤心脏病学',
  '肿瘤治疗相关心功能不全的诊断与监测': '肿瘤心脏病学',
  '肿瘤治疗相关心功能不全的治疗': '肿瘤心脏病学',
  '肿瘤治疗相关QT间期延长': '肿瘤心脏病学',
  '肿瘤相关静脉血栓栓塞症': '肿瘤心脏病学',

  // ── 消化系统 ──
  '肠黏膜屏障': '炎症性肠病',
  '胆道的协调运动': '肝外胆系结石及炎症',
  '肝功能血清指标评估': '肝硬化',
  'Child-Pugh肝功能评分系统': '肝硬化',
  '门静脉血栓与海绵样变': '肝硬化',
  '肝肾综合征': '肝硬化',
  '肝肺综合征': '肝硬化',
  '门静脉血栓的治疗': '肝硬化',
  '肠上皮化生的机制与意义': '胃炎',
  '常用泻剂的分类及机制': '便秘',
};

// ---------------------------------------------------------------------------
// Abbreviation / alias mappings for chapter matching (keyword in title → chapter)
// Extended with additional entries for broader coverage.
// ---------------------------------------------------------------------------
const chapterAliasMap = {
  // ── 呼吸系统 ──
  'COPD': '慢性阻塞性肺疾病',
  '慢阻肺': '慢性阻塞性肺疾病',
  '慢性阻塞性肺': '慢性阻塞性肺疾病',
  '哮喘': '支气管哮喘',
  '支气管扩张': '支气管扩张症',
  '支扩': '支气管扩张症',
  '肺炎': '肺部感染性疾病',
  '社区获得性肺炎': '肺部感染性疾病',
  'CAP': '肺部感染性疾病',
  '医院获得性肺炎': '肺部感染性疾病',
  'HAP': '肺部感染性疾病',
  '流感': '急性上呼吸道感染和急性气管支气管炎',
  '流行性感冒': '急性上呼吸道感染和急性气管支气管炎',
  '上呼吸道感染': '急性上呼吸道感染和急性气管支气管炎',
  '急性气管支气管炎': '急性上呼吸道感染和急性气管支气管炎',
  '急性支气管炎': '急性上呼吸道感染和急性气管支气管炎',
  '慢性支气管炎': '急性上呼吸道感染和急性气管支气管炎',
  '肺脓肿': '肺脓肿',
  '结核': '肺结核',
  '肺结核': '肺结核',
  '肺癌': '肺癌',
  '非小细胞肺癌': '肺癌',
  '小细胞肺癌': '肺癌',
  '间质性肺疾病': '间质性肺疾病',
  'ILD': '间质性肺疾病',
  '肺纤维化': '间质性肺疾病',
  '特发性肺纤维化': '间质性肺疾病',
  'IPF': '间质性肺疾病',
  '结节病': '间质性肺疾病',
  '过敏性肺炎': '间质性肺疾病',
  '肺栓塞': '肺血栓栓塞症',
  'PTE': '肺血栓栓塞症',
  '肺血栓': '肺血栓栓塞症',
  'CTEPH': '肺血栓栓塞症',
  '肺动脉高压': '肺动脉高压',
  '肺心病': '肺动脉高压',
  '慢性肺源性心脏病': '肺动脉高压',
  '胸腔积液': '胸膜疾病',
  '胸膜疾病': '胸膜疾病',
  '气胸': '胸膜疾病',
  '渗出液': '胸膜疾病',
  '漏出液': '胸膜疾病',
  'Light标准': '胸膜疾病',
  '睡眠呼吸': '睡眠呼吸障碍',
  'OSA': '睡眠呼吸障碍',
  '阻塞性睡眠呼吸暂停': '睡眠呼吸障碍',
  'ARDS': '急性呼吸窘迫综合征',
  '急性呼吸窘迫': '急性呼吸窘迫综合征',
  '呼吸衰竭': '呼吸衰竭与呼吸支持技术',
  'ECMO': '呼吸衰竭与呼吸支持技术',
  '氧疗': '呼吸衰竭与呼吸支持技术',
  '烟草': '烟草病学概要',
  '吸烟': '烟草病学概要',
  '曲霉': '肺部感染性疾病',
  '真菌': '肺部感染性疾病',
  '隐球菌': '肺部感染性疾病',
  '肺孢子菌': '肺部感染性疾病',
  '军团菌': '肺部感染性疾病',
  '支原体': '肺部感染性疾病',
  '衣原体': '肺部感染性疾病',
  '新型冠状病毒': '肺部感染性疾病',
  'NTM': '肺结核',
  '非结核分枝杆菌': '肺结核',
  '禽流感': '肺部感染性疾病',

  // ── 循环系统 ──
  '心力衰竭': '心力衰竭',
  '心衰': '心力衰竭',
  '左西孟旦': '心力衰竭',
  '伊伐布雷定': '心力衰竭',
  '新四联': '心力衰竭',
  'NT-proBNP': '心力衰竭',
  'BNP': '心力衰竭',
  '心律失常': '心律失常',
  '房颤': '心律失常',
  '心房颤动': '心律失常',
  '房扑': '心律失常',
  '心房扑动': '心律失常',
  '期前收缩': '心律失常',
  '早搏': '心律失常',
  '心动过速': '心律失常',
  '心动过缓': '心律失常',
  '传导阻滞': '心律失常',
  '束支传导阻滞': '心律失常',
  '窦房结': '心律失常',
  '病态窦房结': '心律失常',
  '窦性停搏': '心律失常',
  '折返': '心律失常',
  '胺碘酮': '心律失常',
  '电复律': '心律失常',
  '电除颤': '心律失常',
  'ICD': '心律失常',
  'CRT': '心律失常',
  'AVNRT': '心律失常',
  'AVRT': '心律失常',
  '室上速': '心律失常',
  '室上性心动过速': '心律失常',
  '室速': '心律失常',
  '心室颤动': '心律失常',
  '心室扑动': '心律失常',
  '预激综合征': '心律失常',
  'WPW': '心律失常',
  'Brugada': '心律失常',
  '长QT': '心律失常',
  'QT间期延长': '心律失常',
  '决奈达隆': '心律失常',
  '尼非卡兰': '心律失常',
  '维拉帕米': '心律失常',
  '腺苷': '心律失常',
  '分支阻滞': '心律失常',
  '左前分支': '心律失常',
  '左后分支': '心律失常',
  '电生理检查': '心律失常',
  '直立倾斜': '心律失常',
  '晕厥': '心律失常',
  '冠心病': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '冠状动脉粥样硬化': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '心绞痛': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '心肌梗死': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '急性冠状动脉综合征': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  'ACS': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  'STEMI': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  'NSTEMI': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '稳定型心绞痛': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '不稳定型心绞痛': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '冠脉痉挛': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '冠状动脉痉挛': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '冠脉造影': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '冠状动脉造影': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '心肌桥': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '微血管疾病': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '溶栓再通': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '再灌注损伤': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '运动负荷': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '运动平板': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '早期复极': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '他汀': '动脉粥样硬化和冠状动脉粥样硬化性心脏病',
  '高血压': '高血压',
  '心肌病': '心肌疾病',
  '肥厚型心肌病': '心肌疾病',
  '扩张型心肌病': '心肌疾病',
  '酒精性心肌病': '心肌疾病',
  '围生期心肌病': '心肌疾病',
  '限制型心肌病': '心肌疾病',
  '先天性心血管': '先天性心血管病',
  '先天性心脏': '先天性心血管病',
  '房间隔缺损': '先天性心血管病',
  '室间隔缺损': '先天性心血管病',
  '动脉导管未闭': '先天性心血管病',
  '法洛四联症': '先天性心血管病',
  '艾森门格': '先天性心血管病',
  '艾森曼格': '先天性心血管病',
  '卵圆孔未闭': '先天性心血管病',
  '肺动脉瓣': '先天性心血管病',
  '冠状动脉瘘': '先天性心血管病',
  '心脏瓣膜': '心脏瓣膜病',
  '瓣膜病': '心脏瓣膜病',
  '主动脉瓣狭窄': '心脏瓣膜病',
  '二尖瓣': '心脏瓣膜病',
  '三尖瓣': '心脏瓣膜病',
  '心脏骤停': '心脏骤停与心脏性猝死',
  '猝死': '心脏骤停与心脏性猝死',
  '心肺复苏': '心脏骤停与心脏性猝死',
  'CPR': '心脏骤停与心脏性猝死',
  'ECPR': '心脏骤停与心脏性猝死',
  '心包': '心包疾病',
  '心内膜炎': '感染性心内膜炎',
  '主动脉夹层': '主动脉和周围血管病',
  '主动脉': '主动脉和周围血管病',
  '下肢动脉': '主动脉和周围血管病',
  '深静脉血栓': '主动脉和周围血管病',
  'DVT': '主动脉和周围血管病',
  '浅静脉血栓': '主动脉和周围血管病',
  '静脉血栓': '主动脉和周围血管病',
  '周围血管': '主动脉和周围血管病',
  '外周动脉': '主动脉和周围血管病',
  '心血管神经症': '心血管神经症',
  '肿瘤心脏病': '肿瘤心脏病学',
  '肿瘤治疗相关': '肿瘤心脏病学',
  '肿瘤相关': '肿瘤心脏病学',

  // ── 消化系统 ──
  '胃食管反流': '胃食管反流病',
  'GERD': '胃食管反流病',
  '食管癌': '食管癌',
  '胃炎': '胃炎',
  '慢性胃炎': '胃炎',
  '急性胃炎': '胃炎',
  '肠上皮化生': '胃炎',
  '消化性溃疡': '消化性溃疡',
  '胃溃疡': '消化性溃疡',
  '十二指肠溃疡': '消化性溃疡',
  '胃癌': '胃癌',
  '肠结核': '肠结核和结核性腹膜炎',
  '结核性腹膜炎': '肠结核和结核性腹膜炎',
  '炎症性肠病': '炎症性肠病',
  '溃疡性结肠炎': '炎症性肠病',
  '克罗恩': '炎症性肠病',
  '肠黏膜屏障': '炎症性肠病',
  '肠黏膜': '炎症性肠病',
  '结直肠癌': '结直肠癌',
  '结肠癌': '结直肠癌',
  '直肠癌': '结直肠癌',
  '功能性消化不良': '功能性胃肠病',
  '肠易激综合征': '功能性胃肠病',
  'IBS': '功能性胃肠病',
  '病毒性肝炎': '病毒性肝炎',
  '乙型肝炎': '病毒性肝炎',
  '丙型肝炎': '病毒性肝炎',
  'HBV': '病毒性肝炎',
  'HCV': '病毒性肝炎',
  '脂肪性肝病': '脂肪性肝病',
  'NAFLD': '脂肪性肝病',
  '酒精性肝病': '脂肪性肝病',
  'ALD': '脂肪性肝病',
  '自身免疫性肝病': '自身免疫性肝病',
  '药物性肝病': '药物性肝病',
  '肝硬化': '肝硬化',
  '肝性脑病': '肝硬化',
  '门脉高压': '肝硬化',
  '门静脉高压': '肝硬化',
  '门静脉血栓': '肝硬化',
  '门静脉': '肝硬化',
  '腹腔积液': '肝硬化',
  '肝功能': '肝硬化',
  'Child-Pugh': '肝硬化',
  'Child分级': '肝硬化',
  'MELD': '肝硬化',
  '肝肾综合征': '肝硬化',
  '肝肺综合征': '肝硬化',
  '原发性肝癌': '原发性肝癌',
  '肝癌': '原发性肝癌',
  '急性肝衰竭': '急性肝衰竭',
  '胆囊结石': '肝外胆系结石及炎症',
  '胆绞痛': '肝外胆系结石及炎症',
  '胆囊炎': '肝外胆系结石及炎症',
  '胆管炎': '肝外胆系结石及炎症',
  '胆石症': '肝外胆系结石及炎症',
  '胆道结石': '肝外胆系结石及炎症',
  '胆道': '肝外胆系结石及炎症',
  '胆道运动': '肝外胆系结石及炎症',
  'ERCP': '肝外胆系结石及炎症',
  '胆囊癌': '胆道系统肿瘤',
  '胆管癌': '胆道系统肿瘤',
  '胰腺炎': '胰腺炎',
  '胰腺癌': '胰腺癌',
  '腹痛': '腹痛',
  '阑尾炎': '腹痛',
  '穿孔': '腹痛',
  '腹泻': '慢性腹泻',
  '便秘': '便秘',
  '泻剂': '便秘',
  '消化道出血': '消化道出血',
  '消化内镜': '胃食管反流病',
  '胃镜': '胃食管反流病',
  '幽门螺杆菌': '消化性溃疡',
  'Hp': '消化性溃疡',

  // ── 泌尿系统 ──
  '肾小球': '原发性肾小球疾病',
  'IgA肾病': '原发性肾小球疾病',
  '肾病综合征': '原发性肾小球疾病',
  '微小病变': '原发性肾小球疾病',
  '膜性肾病': '原发性肾小球疾病',
  '局灶节段': '原发性肾小球疾病',
  '狼疮性肾炎': '继发性肾病',
  '糖尿病肾': '继发性肾病',
  'DKD': '继发性肾病',
  'ANCA': '继发性肾病',
  '间质性肾炎': '间质性肾炎',
  '尿路感染': '尿路感染',
  '肾盂肾炎': '尿路感染',
  '膀胱炎': '尿路感染',
  '肾小管': '肾小管疾病',
  'Fanconi': '肾小管疾病',
  '肾小管酸中毒': '肾小管疾病',
  '肾动脉': '肾血管疾病',
  '肾静脉血栓': '肾血管疾病',
  '肾血管': '肾血管疾病',
  '遗传性肾': '遗传性肾病',
  '急性肾损伤': '急性肾损伤',
  '慢性肾衰竭': '慢性肾衰竭',
  '肾脏替代': '肾脏替代治疗',
  '高尿酸血症性肾': '原发性肾小球疾病',
  '尿酸肾结石': '原发性肾小球疾病',
  '慢性肾炎': '原发性肾小球疾病',
};

// ---------------------------------------------------------------------------
// All valid chapter names (flattened for quick lookup)
// ---------------------------------------------------------------------------
const allChapters = new Set(
  Object.values(internalMedicineStructure).flat()
);

// ---------------------------------------------------------------------------
// Helper: extract system short name from subject
// ---------------------------------------------------------------------------
function extractSystem(subject) {
  // Direct lookup
  if (subjectToSystem[subject]) return subjectToSystem[subject];

  const match = subject.match(/内科学\s*-\s*(.+)/);
  if (!match) return null;
  const suffix = match[1].trim();

  // Try to match prefix against known full names
  for (const [full, short] of Object.entries(subjectToSystem)) {
    const fullSuffix = full.replace(/内科学\s*-\s*/, '');
    if (suffix === fullSuffix || suffix.startsWith(fullSuffix.replace('疾病', ''))) {
      return short;
    }
  }

  // Try partial matching on system keywords embedded in the suffix
  if (suffix.includes('呼吸')) return '呼吸系统';
  if (suffix.includes('循环')) return '循环系统';
  if (suffix.includes('消化')) return '消化系统';
  if (suffix.includes('泌尿') || suffix.includes('肾')) return '泌尿系统';
  if (suffix.includes('血液')) return '血液系统';
  if (suffix.includes('内分泌') || suffix.includes('代谢')) return '内分泌和代谢性疾病';
  if (suffix.includes('风湿')) return '风湿免疫病';
  if (suffix.includes('理化')) return '理化因素所致疾病';
  if (suffix.includes('肿瘤')) return '循环系统'; // 肿瘤心脏病学 is in 循环系统

  return null;
}

// ---------------------------------------------------------------------------
// Match title to chapter
// ---------------------------------------------------------------------------
function matchChapter(title, systemName) {
  const chapters = internalMedicineStructure[systemName];
  if (!chapters) return null;

  // 1. Check if any chapter name is contained in the title (high confidence)
  for (const ch of chapters) {
    if (title.includes(ch)) {
      return ch;
    }
  }

  // 2. Check abbreviation / alias map — find all matching aliases, prefer the longest
  let bestAliasMatch = null;
  let bestAliasLength = 0;
  for (const [alias, chName] of Object.entries(chapterAliasMap)) {
    if (title.includes(alias) && chapters.includes(chName)) {
      if (alias.length > bestAliasLength) {
        bestAliasLength = alias.length;
        bestAliasMatch = chName;
      }
    }
  }
  if (bestAliasMatch) return bestAliasMatch;

  // 3. Fuzzy: extract meaningful keywords from the title and score chapters
  const noiseWords = new Set([
    '的', '与', '和', '在', '中', '内', '对', '从', '用', '型', '期',
    '治疗', '诊断', '表现', '机制', '病理', '生理', '病因', '临床',
    '检查', '特点', '评估', '原则', '定义', '分类', '鉴别', '流行病学',
    '预防', '预后', '并发症', '概述', '标准', '价值', '意义', '特征',
    '学', '方法', '指标', '应用', '策略', '处理', '分级', '分型',
    '核心', '关键', '常见', '典型', '基本', '主要', '严重', '急性',
    '慢性', '特殊', '其他', '相关',
  ]);

  const titleTokens = [];
  const parts = title.split(/[（）()、/，,：:；;。\s]+/).filter(Boolean);
  for (const part of parts) {
    if (part.length <= 4) {
      if (part.length >= 3 && !noiseWords.has(part)) {
        titleTokens.push(part);
      }
    } else {
      titleTokens.push(part);
    }
  }

  let bestChapter = null;
  let bestScore = 0;

  for (const ch of chapters) {
    if (ch.length <= 4) {
      if (title.includes(ch)) return ch;
    }

    let overlap = 0;
    for (const chChar of ch) {
      if (title.includes(chChar)) overlap++;
    }
    const score = overlap / ch.length;

    let tokenBonus = 0;
    for (const token of titleTokens) {
      if (token.length >= 3 && ch.includes(token)) {
        tokenBonus += token.length * 2;
      }
    }

    const totalScore = score + tokenBonus / ch.length;
    if (totalScore > bestScore) {
      bestScore = totalScore;
      bestChapter = ch;
    }
  }

  if (bestScore >= 0.35) {
    return bestChapter;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  const content = fs.readFileSync(FILE_PATH, 'utf-8');
  const lines = content.split('\n');

  // ---- Phase 1: strip all existing "chapter": lines ----
  const chapterLineRegex = /^\s*"chapter":\s*"[^"]*",?\s*$/;
  const filteredLines = lines.filter(line => !chapterLineRegex.test(line));

  console.log(`Stripped ${lines.length - filteredLines.length} existing "chapter" lines.`);

  // ---- Phase 2: parse node blocks in the cleaned content ----
  const nodeBlocks = [];
  let inArray = false;
  let braceDepth = 0;
  let blockStart = -1;

  for (let i = 0; i < filteredLines.length; i++) {
    const line = filteredLines[i];
    if (!inArray) {
      if (line.includes('export const extractedKnowledgeNodes')) {
        inArray = true;
      }
      continue;
    }

    for (let j = 0; j < line.length; j++) {
      const ch = line[j];
      if (ch === '{') {
        if (braceDepth === 0) {
          blockStart = i;
        }
        braceDepth++;
      } else if (ch === '}') {
        braceDepth--;
        if (braceDepth === 0 && blockStart >= 0) {
          nodeBlocks.push({ start: blockStart, end: i });
          blockStart = -1;
        }
      }
    }
  }

  console.log(`Found ${nodeBlocks.length} node blocks to process.`);

  // ---- Phase 3: determine chapter for each node and insert ----
  let matchedCount = 0;
  let otherCount = 0;
  const results = { matched: {}, other: [] };

  // Process blocks in reverse so index insertions don't shift earlier blocks
  for (let bi = nodeBlocks.length - 1; bi >= 0; bi--) {
    const block = nodeBlocks[bi];
    const blockLines = filteredLines.slice(block.start, block.end + 1);
    const blockText = blockLines.join('\n');

    // Extract id
    const idMatch = blockText.match(/"id":\s*"([^"]+)"/);
    if (!idMatch) continue;
    const nodeId = idMatch[1];

    // Extract title
    const titleMatch = blockText.match(/"title":\s*"([^"]+)"/);
    if (!titleMatch) continue;
    const title = titleMatch[1];

    // Extract subject
    const subjectMatch = blockText.match(/"subject":\s*"([^"]+)"/);
    if (!subjectMatch) continue;
    const subject = subjectMatch[1];

    let chapter = '其他';

    // Priority 1: exact title override
    if (titleOverrideMap[title]) {
      chapter = titleOverrideMap[title];
    } else {
      // Priority 2-4: normal system-based matching
      const systemName = extractSystem(subject);
      if (systemName) {
        const matched = matchChapter(title, systemName);
        if (matched) {
          chapter = matched;
        }
      }
    }

    if (chapter === '其他') {
      otherCount++;
      results.other.push({ id: nodeId, title, subject });
    } else {
      matchedCount++;
      results.matched[chapter] = (results.matched[chapter] || 0) + 1;
    }

    // Insert chapter line after the subject line
    for (let i = block.start; i <= block.end; i++) {
      const line = filteredLines[i];
      if (line.includes('"subject":')) {
        const indent = line.match(/^(\s*)/)[1];
        const chapterLine = `${indent}"chapter": "${chapter}",`;
        filteredLines.splice(i + 1, 0, chapterLine);
        break;
      }
    }
  }

  // ---- Phase 4: write back ----
  fs.writeFileSync(FILE_PATH, filteredLines.join('\n'), 'utf-8');

  // ---- Phase 5: report ----
  console.log('\n=== RESULTS ===');
  console.log(`Total nodes: ${matchedCount + otherCount}`);
  console.log(`Matched to chapter: ${matchedCount}`);
  console.log(`Fell back to '其他': ${otherCount}`);

  console.log('\n--- Matched chapters breakdown ---');
  const sorted = Object.entries(results.matched).sort((a, b) => b[1] - a[1]);
  for (const [ch, count] of sorted) {
    console.log(`  ${ch}: ${count}`);
  }

  if (results.other.length > 0) {
    console.log(`\n--- Nodes that fell back to '其他' (${results.other.length}) ---`);
    for (const node of results.other) {
      console.log(`  [${node.id}] "${node.title}" (subject: ${node.subject})`);
    }
  } else {
    console.log('\nAll nodes matched to a chapter!');
  }
}

main();

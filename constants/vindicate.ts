/**
 * VINDICATE 鉴别诊断分类框架
 * 基于 PRD 第 57 章
 */

export interface VINDICATECategory {
  letter: string
  name: string
  nameEn: string
  subcategories: {
    name: string
    examples: string[]
  }[]
}

export const VINDICATE_CATEGORIES: VINDICATECategory[] = [
  {
    letter: 'V',
    name: '血管性',
    nameEn: 'Vascular',
    subcategories: [
      { name: '动脉', examples: ['主动脉夹层', 'AMI', '脑卒中', '肠系膜缺血'] },
      { name: '静脉', examples: ['DVT', 'PE', '深静脉血栓'] },
      { name: '微血管', examples: ['TTP', 'HUS', 'DIC'] },
    ],
  },
  {
    letter: 'I',
    name: '感染性',
    nameEn: 'Infectious',
    subcategories: [
      { name: '细菌', examples: ['肺炎', '脑膜炎', '尿路感染', '败血症'] },
      { name: '病毒', examples: ['流感', 'COVID', '脑炎'] },
      { name: '真菌', examples: ['念珠菌', '曲霉菌'] },
      { name: '寄生虫', examples: ['疟疾', '阿米巴'] },
    ],
  },
  {
    letter: 'N',
    name: '肿瘤性',
    nameEn: 'Neoplastic',
    subcategories: [
      { name: '实体瘤', examples: ['肺癌', '乳腺癌', '结直肠癌'] },
      { name: '血液肿瘤', examples: ['白血病', '淋巴瘤', '多发性骨髓瘤'] },
      { name: '良性', examples: ['脑膜瘤', '子宫肌瘤'] },
    ],
  },
  {
    letter: 'D',
    name: '退行性',
    nameEn: 'Degenerative',
    subcategories: [
      { name: '骨关节', examples: ['骨关节炎', '椎间盘退变'] },
      { name: '神经', examples: ['阿尔茨海默病', '帕金森病'] },
      { name: '其他', examples: ['黄斑变性', 'COPD'] },
    ],
  },
  {
    letter: 'I',
    name: '医源性/中毒性',
    nameEn: 'Iatrogenic/Intoxication',
    subcategories: [
      { name: '药物', examples: ['药物副作用', '药物相互作用'] },
      { name: '毒物', examples: ['酒精中毒', '重金属', '有机磷'] },
      { name: '医源性', examples: ['放射性肠炎', '导管感染'] },
    ],
  },
  {
    letter: 'C',
    name: '先天性',
    nameEn: 'Congenital',
    subcategories: [
      { name: '心脏', examples: ['先天性心脏病（ASD/VSD/PDA）'] },
      { name: '遗传', examples: ['马凡综合征', '囊性纤维化', '镰状细胞病'] },
      { name: '发育', examples: ['先天性巨结肠', '食管闭锁'] },
    ],
  },
  {
    letter: 'A',
    name: '自身免疫性',
    nameEn: 'Autoimmune',
    subcategories: [
      { name: '系统性', examples: ['SLE', '类风湿关节炎', '血管炎'] },
      { name: '器官特异', examples: ['1型糖尿病', 'Graves病', 'MS'] },
      { name: '过敏', examples: ['哮喘', '过敏性鼻炎'] },
    ],
  },
  {
    letter: 'T',
    name: '外伤性',
    nameEn: 'Traumatic',
    subcategories: [
      { name: '钝器', examples: ['骨折', '硬膜下血肿', '脾破裂'] },
      { name: '穿透', examples: ['刺伤', '枪伤'] },
      { name: '其他', examples: ['烧伤', '冻伤', '电击伤'] },
    ],
  },
  {
    letter: 'E',
    name: '内分泌/代谢性',
    nameEn: 'Endocrine/Metabolic',
    subcategories: [
      { name: '腺体', examples: ['甲亢/甲减', '库欣', 'Addison'] },
      { name: '糖代谢', examples: ['糖尿病', 'DKA', '低血糖'] },
      { name: '电解质', examples: ['低钾', '高钙', '低钠'] },
      { name: '酸碱', examples: ['代酸', '代碱', '呼酸', '呼碱'] },
    ],
  },
]

/**
 * 病例阶段枚举（PRD 11.3）
 */
export enum CasePhase {
  INTRO = 'intro',
  HISTORY = 'history',
  EXAM = 'exam',
  TESTS = 'tests',
  DIAGNOSIS = 'diagnosis',
  TREATMENT = 'treatment',
  SCORING = 'scoring',
  FEEDBACK = 'feedback',
}

export const PHASE_ORDER = [
  CasePhase.INTRO,
  CasePhase.HISTORY,
  CasePhase.EXAM,
  CasePhase.TESTS,
  CasePhase.DIAGNOSIS,
  CasePhase.TREATMENT,
  CasePhase.SCORING,
  CasePhase.FEEDBACK,
]

export const PHASE_LABELS: Record<CasePhase, string> = {
  [CasePhase.INTRO]: '接诊',
  [CasePhase.HISTORY]: '问诊',
  [CasePhase.EXAM]: '查体',
  [CasePhase.TESTS]: '检查',
  [CasePhase.DIAGNOSIS]: '诊断',
  [CasePhase.TREATMENT]: '治疗',
  [CasePhase.SCORING]: '评分',
  [CasePhase.FEEDBACK]: '反馈',
}

/**
 * 主诉分类（PRD 11.4）
 */
export const CHIEF_COMPLAINTS = [
  { id: 'chest_pain', label: '胸痛', icon: '❤️' },
  { id: 'dyspnea', label: '呼吸困难', icon: '🫁' },
  { id: 'abdominal_pain', label: '腹痛', icon: '🤢' },
  { id: 'fever', label: '发热', icon: '🌡️' },
  { id: 'ams', label: '意识改变', icon: '🧠' },
] as const

export type ChiefComplaintId = (typeof CHIEF_COMPLAINTS)[number]['id']

/**
 * 查体区域
 */
export const EXAM_REGIONS = [
  { id: 'general', label: '一般检查' },
  { id: 'vital_signs', label: '生命体征' },
  { id: 'cardiovascular', label: '心血管' },
  { id: 'respiratory', label: '呼吸系统' },
  { id: 'abdominal', label: '腹部' },
  { id: 'neurological', label: '神经系统' },
  { id: 'extremities', label: '四肢' },
] as const

/**
 * 检查项目
 */
export const LAB_TESTS = [
  { id: 'ecg', label: '心电图', category: 'cardiac' },
  { id: 'troponin', label: '肌钙蛋白', category: 'cardiac' },
  { id: 'bnp', label: 'BNP', category: 'cardiac' },
  { id: 'cbc', label: '血常规', category: 'blood' },
  { id: 'bmp', label: '生化', category: 'blood' },
  { id: 'coagulation', label: '凝血', category: 'blood' },
  { id: 'd_dimer', label: 'D-二聚体', category: 'blood' },
  { id: 'abg', label: '血气分析', category: 'blood' },
  { id: 'glucose', label: '血糖', category: 'blood' },
  { id: 'thyroid', label: '甲状腺功能', category: 'blood' },
  { id: 'chest_xray', label: '胸片', category: 'imaging' },
  { id: 'echo', label: '心脏超声', category: 'imaging' },
  { id: 'ct_chest', label: '胸部CT', category: 'imaging' },
  { id: 'ct_head', label: '头颅CT', category: 'imaging' },
  { id: 'cta_pulmonary', label: '肺动脉CTA', category: 'imaging' },
  { id: 'cta_aorta', label: '主动脉CTA', category: 'imaging' },
] as const

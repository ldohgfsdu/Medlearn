/**
 * Intent Parser - 用户意图解析器
 * 基于 PRD 第 66 章和第 64.3 章
 *
 * 规则匹配覆盖 82% 的用户输入（<10ms，$0）
 * LLM Fallback 处理剩余 18%
 */

import { CasePhase } from '@/constants/vindicate'

// ============================================
// 类型定义
// ============================================

export type IntentType =
  | 'ask_history'
  | 'physical_exam'
  | 'order_test'
  | 'mention_diagnosis'
  | 'mention_treatment'
  | 'phase_transition'
  | 'off_topic'
  | 'greeting'
  | 'empty'
  | 'unknown'

const INTENT_TYPES = new Set<IntentType>([
  'ask_history',
  'physical_exam',
  'order_test',
  'mention_diagnosis',
  'mention_treatment',
  'phase_transition',
  'off_topic',
  'greeting',
  'empty',
  'unknown',
])

export function isIntentType(value: string | null | undefined): value is IntentType {
  return typeof value === 'string' && INTENT_TYPES.has(value as IntentType)
}

export interface Intent {
  type: IntentType
  target?: string
  confidence: number
  rawInput: string
  matchedRule?: string
  needsLLM?: boolean
}

interface IntentRule {
  name: string
  patterns: RegExp[]
  intent: { type: IntentType; target?: string }
  confidence: number
  phase?: CasePhase[]
}

// ============================================
// 规则库
// ============================================

const INTENT_RULES: IntentRule[] = [
  // ---- 问病史 (ask_history) ----
  // HPI - 发病时间
  {
    name: 'hpi_onset',
    patterns: [
      /什么时候开始/,
      /何时开始/,
      /多久了/,
      /多长时间/,
      /发病时间/,
      /从什么时候/,
      /几时起/,
      /开始疼/,
      /几号开始/,
    ],
    intent: { type: 'ask_history', target: 'hpi_onset' },
    confidence: 0.95,
    phase: [CasePhase.INTRO, CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 持续时间
  {
    name: 'hpi_duration',
    patterns: [
      /持续.{0,50}多久/,
      /疼了.{0,50}久/,
      /多.{0,50}久/,
      /一直.{0,50}吗/,
      /没停过/,
      /持续时间/,
    ],
    intent: { type: 'ask_history', target: 'hpi_duration' },
    confidence: 0.95,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 疼痛性质
  {
    name: 'hpi_character',
    patterns: [
      /什么.{0,50}(样|种).{0,50}疼/,
      /怎么.{0,50}疼/,
      /疼痛.{0,50}性质/,
      /疼痛.{0,50}类型/,
      /什么样的/,
      /描述.{0,50}疼/,
      /感觉.{0,50}疼/,
      /闷痛|绞痛|压榨|撕裂|刺痛|钝痛/,
    ],
    intent: { type: 'ask_history', target: 'hpi_character' },
    confidence: 0.95,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 疼痛部位
  {
    name: 'hpi_location',
    patterns: [
      /疼在哪/,
      /哪里.{0,50}疼/,
      /疼痛.{0,50}位置/,
      /疼痛.{0,50}部位/,
      /什么地方/,
      /哪个位置/,
    ],
    intent: { type: 'ask_history', target: 'hpi_location' },
    confidence: 0.95,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 放射痛
  {
    name: 'hpi_radiation',
    patterns: [
      /放射/,
      /别的.{0,50}地方.{0,50}疼/,
      /其他.{0,50}部位/,
      /肩膀|手臂|后背|下巴|牙齿/,
      /传导/,
    ],
    intent: { type: 'ask_history', target: 'hpi_radiation' },
    confidence: 0.9,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 疼痛程度
  {
    name: 'hpi_severity',
    patterns: [
      /多.{0,50}疼/,
      /疼痛.{0,50}程度/,
      /几分/,
      /严重/,
      /剧烈/,
      /能忍受/,
    ],
    intent: { type: 'ask_history', target: 'hpi_severity' },
    confidence: 0.9,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 加重因素
  {
    name: 'hpi_aggravating',
    patterns: [
      /什么.{0,50}加重/,
      /加重.{0,50}因素/,
      /什么时候.{0,50}更/,
      /活动.{0,50}加重/,
      /动.{0,50}疼/,
      /什么.{0,50}时候.{0,50}严重/,
    ],
    intent: { type: 'ask_history', target: 'hpi_aggravating' },
    confidence: 0.9,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 缓解因素
  {
    name: 'hpi_relieving',
    patterns: [
      /什么.{0,50}缓解/,
      /缓解.{0,50}因素/,
      /怎么.{0,50}能.{0,50}好/,
      /休息.{0,50}好/,
      /怎么.{0,50}减轻/,
    ],
    intent: { type: 'ask_history', target: 'hpi_relieving' },
    confidence: 0.9,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 伴随症状
  {
    name: 'hpi_associated',
    patterns: [
      /伴随.{0,50}症状/,
      /还有.{0,50}不舒服/,
      /还有什么/,
      /其他.{0,50}症状/,
      /有.{0,10}呼吸困难/,
      /呼吸困难.{0,10}吗/,
      /出汗|恶心|呕吐|头晕|呼吸困难|胸闷/,
    ],
    intent: { type: 'ask_history', target: 'hpi_associated' },
    confidence: 0.85,
    phase: [CasePhase.INTRO, CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 开放问诊
  {
    name: 'hpi_open',
    patterns: [
      /怎么了/,
      /哪儿不舒服/,
      /哪里不舒服/,
      /什么地方不舒服/,
      /什么不舒服/,
      /怎么不舒服/,
      /哪里难受/,
      /什么症状/,
      /什么不适/,
    ],
    intent: { type: 'unknown' },
    confidence: 0.8,
    phase: [CasePhase.INTRO, CasePhase.HISTORY, CasePhase.EXAM],
  },
  // HPI - 既往发作
  {
    name: 'hpi_previous',
    patterns: [
      /以前.{0,50}有过/,
      /之前.{0,50}有过/,
      /以前.{0,50}类似/,
      /第.*次/,
    ],
    intent: { type: 'ask_history', target: 'hpi_previous' },
    confidence: 0.9,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // PMH - 既往病史
  {
    name: 'pmh_diseases',
    patterns: [
      /既往.{0,50}病/,
      /以前.{0,50}病/,
      /基础.{0,50}疾病/,
      /有什么.{0,50}病/,
      /病史/,
      /高血压|糖尿病|心脏病|脑梗/,
    ],
    intent: { type: 'ask_history', target: 'pmh_diseases' },
    confidence: 0.9,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // 用药史
  {
    name: 'medications',
    patterns: [
      /吃.{0,50}什么药/,
      /用药/,
      /药物/,
      /在.{0,50}服/,
      /每天.{0,50}吃/,
    ],
    intent: { type: 'ask_history', target: 'medications' },
    confidence: 0.9,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // 过敏史
  {
    name: 'allergies',
    patterns: [
      /过敏/,
      /药物.{0,50}过敏/,
      /对.{0,50}过敏/,
    ],
    intent: { type: 'ask_history', target: 'allergies' },
    confidence: 0.95,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // 吸烟史
  {
    name: 'social_smoking',
    patterns: [
      /吸烟/,
      /抽烟/,
      /烟龄/,
      /一天.{0,50}包/,
    ],
    intent: { type: 'ask_history', target: 'social_smoking' },
    confidence: 0.95,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // 饮酒史
  {
    name: 'social_alcohol',
    patterns: [
      /饮酒/,
      /喝酒/,
      /酒量/,
    ],
    intent: { type: 'ask_history', target: 'social_alcohol' },
    confidence: 0.95,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },
  // 家族史
  {
    name: 'family_history',
    patterns: [
      /家族史/,
      /家人.{0,50}病/,
      /父母.{0,50}病/,
      /遗传/,
    ],
    intent: { type: 'ask_history', target: 'family_history' },
    confidence: 0.95,
    phase: [CasePhase.HISTORY, CasePhase.EXAM],
  },

  // ---- 查体 (physical_exam) ----
  {
    name: 'exam_vital_signs',
    patterns: [
      /量.*血压/,
      /测.*血压/,
      /生命体征/,
      /血压.*心率/,
      /量.*体温/,
    ],
    intent: { type: 'physical_exam', target: 'vital_signs' },
    confidence: 0.95,
    phase: [CasePhase.EXAM, CasePhase.HISTORY],
  },
  {
    name: 'exam_cardiovascular',
    patterns: [
      /听.*心脏/,
      /心脏.*听诊/,
      /心音/,
      /查.*心脏/,
      /心血管/,
    ],
    intent: { type: 'physical_exam', target: 'cardiovascular' },
    confidence: 0.95,
    phase: [CasePhase.EXAM, CasePhase.HISTORY],
  },
  {
    name: 'exam_respiratory',
    patterns: [
      /听.*肺/,
      /肺.*听诊/,
      /呼吸音/,
      /查.*肺/,
      /呼吸系统/,
    ],
    intent: { type: 'physical_exam', target: 'respiratory' },
    confidence: 0.95,
    phase: [CasePhase.EXAM, CasePhase.HISTORY],
  },
  {
    name: 'exam_abdominal',
    patterns: [
      /查.*腹部/,
      /肚子/,
      /腹部.*触诊/,
      /腹部.*听诊/,
    ],
    intent: { type: 'physical_exam', target: 'abdominal' },
    confidence: 0.95,
    phase: [CasePhase.EXAM, CasePhase.HISTORY],
  },
  {
    name: 'exam_neurological',
    patterns: [
      /神经.*系统/,
      /查.*神经/,
      /肌力|反射|病理征/,
    ],
    intent: { type: 'physical_exam', target: 'neurological' },
    confidence: 0.9,
    phase: [CasePhase.EXAM, CasePhase.HISTORY],
  },
  {
    name: 'exam_extremities',
    patterns: [
      /查.*四肢/,
      /下肢.*水肿/,
      /肢体/,
      /四肢/,
    ],
    intent: { type: 'physical_exam', target: 'extremities' },
    confidence: 0.9,
    phase: [CasePhase.EXAM, CasePhase.HISTORY],
  },

  // ---- 开检查 (order_test) ----
  {
    name: 'test_ecg',
    patterns: [
      /做.*心电图/,
      /查.*心电图/,
      /ECG|EKG/,
      /心电图/,
    ],
    intent: { type: 'order_test', target: 'ecg' },
    confidence: 0.95,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },
  {
    name: 'test_troponin',
    patterns: [
      /查.*肌钙蛋白/,
      /肌钙蛋白/,
      /肌钙|cTn|TnI|TnT/,
    ],
    intent: { type: 'order_test', target: 'troponin' },
    confidence: 0.95,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },
  {
    name: 'test_bnp',
    patterns: [
      /查.*BNP|查.*NT.?proBNP/,
      /BNP/,
      /脑钠肽/,
    ],
    intent: { type: 'order_test', target: 'bnp' },
    confidence: 0.95,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },
  {
    name: 'test_cbc',
    patterns: [
      /查.*血常规/,
      /血常规/,
      /血细胞/,
    ],
    intent: { type: 'order_test', target: 'cbc' },
    confidence: 0.95,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },
  {
    name: 'test_bmp',
    patterns: [
      /查.*生化/,
      /生化/,
      /肝肾功能/,
      /电解质/,
    ],
    intent: { type: 'order_test', target: 'bmp' },
    confidence: 0.9,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },
  {
    name: 'test_d_dimer',
    patterns: [
      /查.*D.?二聚体/,
      /D.?二聚体/,
    ],
    intent: { type: 'order_test', target: 'd_dimer' },
    confidence: 0.95,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },
  {
    name: 'test_chest_xray',
    patterns: [
      /拍.*胸片/,
      /胸片/,
      /X光/,
      /胸部.*平片/,
    ],
    intent: { type: 'order_test', target: 'chest_xray' },
    confidence: 0.95,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },
  {
    name: 'test_echo',
    patterns: [
      /心脏.*超声/,
      /超声.*心动/,
      /心脏.*彩超/,
      /echo/,
    ],
    intent: { type: 'order_test', target: 'echo' },
    confidence: 0.9,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },
  {
    name: 'test_ct_chest',
    patterns: [
      /胸部.*CT/,
      /肺.*CT/,
      /CT.*胸/,
    ],
    intent: { type: 'order_test', target: 'ct_chest' },
    confidence: 0.9,
    phase: [CasePhase.TESTS, CasePhase.EXAM],
  },

  // ---- 提及诊断 (mention_diagnosis) ----
  {
    name: 'mention_diagnosis',
    patterns: [
      /诊断.{0,50}是/,
      /考虑.{0,50}是/,
      /可能是/,
      /应该是/,
      /我.{0,50}诊断/,
      /我.{0,50}认为/,
      /怀疑.{0,50}是/,
    ],
    intent: { type: 'mention_diagnosis' },
    confidence: 0.85,
    phase: [CasePhase.DIAGNOSIS, CasePhase.EXAM, CasePhase.TESTS],
  },

  // ---- 提及治疗 (mention_treatment) ----
  {
    name: 'mention_treatment',
    patterns: [
      /治疗.{0,50}方案/,
      /用药/,
      /手术/,
      /介入/,
      /支架/,
      /溶栓/,
    ],
    intent: { type: 'mention_treatment' },
    confidence: 0.85,
    phase: [CasePhase.DIAGNOSIS, CasePhase.TREATMENT],
  },

  // ---- 问候 ----
  {
    name: 'greeting',
    patterns: [
      /^(你好|hi|hello|hey|嗨|您好)/i,
    ],
    intent: { type: 'greeting' },
    confidence: 0.95,
  },

  // ---- 跑题 ----
  {
    name: 'off_topic',
    patterns: [
      /今天.{0,50}天气/,
      /你.{0,50}几岁/,
      /你是.{0,50}谁/,
      /聊.{0,50}别的/,
      /无关.{0,50}话题/,
    ],
    intent: { type: 'off_topic' },
    confidence: 0.9,
  },
]

// ============================================
// Intent Parser
// ============================================

export class IntentParser {
  private rules = INTENT_RULES

  /**
   * 解析用户输入的意图
   * 规则匹配覆盖 ~82% 的输入
   */
  parse(input: string, currentPhase: CasePhase): Intent {
    const cleaned = input
      .trim()
      .replace(/[,，。.！!？?]+$/g, '')
      .replace(/\s+/g, ' ')

    // 空输入
    if (!cleaned || cleaned.length < 1) {
      return { type: 'empty', confidence: 1.0, rawInput: input }
    }

    // 规则匹配
    for (const rule of this.rules) {
      // 检查阶段限制（接诊阶段允许病史类与开放提问规则）
      if (
        rule.phase &&
        !rule.phase.includes(currentPhase) &&
        !(
          currentPhase === CasePhase.INTRO &&
          (rule.intent.type === 'ask_history' || rule.intent.type === 'unknown')
        )
      ) {
        continue
      }

      for (const pattern of rule.patterns) {
        if (pattern.test(cleaned)) {
          return {
            type: rule.intent.type,
            target: rule.intent.target,
            confidence: rule.confidence,
            rawInput: input,
            matchedRule: rule.name,
          }
        }
      }
    }

    // 默认：需要 LLM 处理
    return {
      type: 'unknown',
      confidence: 0.0,
      rawInput: input,
      needsLLM: true,
    }
  }

  /**
   * 检查是否为诊断相关输入
   */
  isDiagnosisMention(input: string): boolean {
    const patterns = [
      /诊断.{0,50}是/,
      /考虑.{0,50}是/,
      /可能是/,
      /应该是/,
      /我.{0,50}诊断/,
      /我.{0,50}认为/,
      /怀疑.{0,50}是/,
    ]
    return patterns.some((p) => p.test(input))
  }

  /**
   * 检查是否为治疗相关输入
   */
  isTreatmentMention(input: string): boolean {
    const patterns = [
      /治疗.{0,50}方案/,
      /用药/,
      /手术/,
      /介入/,
      /支架/,
      /溶栓/,
    ]
    return patterns.some((p) => p.test(input))
  }
}

export const intentParser = new IntentParser()

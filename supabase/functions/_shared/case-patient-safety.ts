// Pure safety checks kept deterministic for regression testing.
export interface DiagnosisAnswerKey {
  primary: string
  primaryAliases?: string[]
}

const INJECTION_PATTERNS = [
  /ignore (all |any )?(previous|prior|above) instructions/i,
  /system (prompt|message|instruction)/i,
  /developer (prompt|message|instruction)/i,
  /jailbreak|prompt injection/i,
  /reveal (the )?(diagnosis|answer|rubric)/i,
  /act as (a )?(doctor|clinician|system)/i,
  /忽略.{0,8}(之前|以上|前面).{0,8}(指令|要求|规则)/,
  /(系统|开发者).{0,4}(提示词|消息|指令)/,
  /(告诉|泄露|输出|显示).{0,8}(诊断|答案|评分规则|标准答案)/,
  /(跳出|退出|忘记).{0,6}(患者|角色|设定)/,
  /越狱|提示词注入/,
]

const UNSAFE_ADVICE_PATTERNS = [
  /(我建议你|你应该|你需要).{0,20}(服用|使用|停用|加量|减量|治疗|手术)/,
  /(治疗方案|处方|用药建议)(是|包括|：|:)/,
  /\b(i recommend|you should|you need to)\b.{0,40}\b(take|stop|increase|decrease|treat|surgery)\b/i,
]

function normalize(value: string): string {
  return value
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[\s\p{P}\p{S}]/gu, '')
}

function containsTerm(content: string, term: string): boolean {
  const trimmed = term.trim()
  if (!trimmed) return false

  if (/^[a-z0-9]+$/i.test(trimmed) && trimmed.length <= 4) {
    return new RegExp(`(^|[^a-z0-9])${trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}([^a-z0-9]|$)`, 'i')
      .test(content)
  }

  const normalizedTerm = normalize(trimmed)
  return normalizedTerm.length >= 2 && normalize(content).includes(normalizedTerm)
}

export function detectPromptInjection(input: string): string | null {
  const match = INJECTION_PATTERNS.find((pattern) => pattern.test(input))
  return match ? match.source : null
}

export function findDiagnosisLeak(
  output: string,
  diagnosis: DiagnosisAnswerKey,
): string | null {
  const terms = [diagnosis.primary, ...(diagnosis.primaryAliases ?? [])]
    .filter((term, index, all) => term && all.indexOf(term) === index)
    .sort((left, right) => right.length - left.length)
  return terms.find((term) => containsTerm(output, term)) ?? null
}

export function detectUnsafeClinicalAdvice(output: string): string | null {
  const match = UNSAFE_ADVICE_PATTERNS.find((pattern) => pattern.test(output))
  return match ? match.source : null
}

export interface SearchIntent {
  diseaseQuery: string
  aspect: string | null
  aspectLabel: string | null
}

const ASPECT_RULES: Array<{ aspect: string; label: string; pattern: RegExp }> = [
  { aspect: 'differential_diagnosis', label: '鉴别诊断', pattern: /鉴别诊断|诊断与鉴别/u },
  { aspect: 'clinical_manifestation', label: '临床表现', pattern: /临床表现|临床特征|症状|体征/u },
  { aspect: 'epidemiology', label: '流行病学', pattern: /流行病学/u },
  { aspect: 'pathogenesis', label: '发病机制', pattern: /发病机制|病理生理|机制|病理/u },
  { aspect: 'treatment', label: '治疗方案', pattern: /治疗方案|治疗原则|治疗|用药|药物/u },
  { aspect: 'diagnosis', label: '诊断与检查', pattern: /诊断标准|辅助检查|实验室检查|影像学|诊断|检查/u },
  { aspect: 'etiology', label: '病因', pattern: /病因|危险因素/u },
  { aspect: 'definition', label: '定义', pattern: /定义|概念/u },
  { aspect: 'prognosis', label: '预后', pattern: /预后|并发症/u },
  { aspect: 'prevention', label: '预防', pattern: /预防/u },
]

export function normalizeSearchText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[\s，。；：、（）()【】《》"'“”‘’]/gu, '')
}

export function parseKnowledgeSearchIntent(query: string): SearchIntent {
  const normalized = normalizeSearchText(query)
  const rule = ASPECT_RULES.find((item) => item.pattern.test(normalized))
  if (!rule) {
    return { diseaseQuery: normalized, aspect: null, aspectLabel: null }
  }

  return {
    diseaseQuery: normalized.replace(rule.pattern, '').replace(/的$/u, ''),
    aspect: rule.aspect,
    aspectLabel: rule.label,
  }
}

export function diseaseSearchScore(
  intent: SearchIntent,
  canonicalName: string,
  aliases: string[] = [],
): number | null {
  const needle = intent.diseaseQuery
  if (!needle) return null
  const canonical = normalizeSearchText(canonicalName)
  const normalizedAliases = aliases.map(normalizeSearchText)
  if (canonical === needle) return 0
  if (normalizedAliases.includes(needle)) return 1
  if (canonical.includes(needle) || needle.includes(canonical)) return 2
  if (normalizedAliases.some((alias) => alias.includes(needle) || needle.includes(alias))) return 3
  return null
}

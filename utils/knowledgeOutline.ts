import { parseContentPoints } from './structuredContent'

export interface RawKnowledgeSection {
  title: string
  content: string
}

export interface KnowledgeSection extends RawKnowledgeSection {
  digest: string[]
}

export interface KnowledgeGroup {
  title: string
  sections: KnowledgeSection[]
}

export interface KnowledgeOutline {
  grouped: boolean
  overview: string[]
  groups: KnowledgeGroup[]
}

interface TopicMarker {
  index: number
  end: number
  order: number
  title: string
}

const CHINESE_NUMBERS: Record<string, number> = {
  一: 1,
  二: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
  十: 10,
}

const TOPIC_HEADING = /(?:^|\s)([一二三四五六七八九十]+)[、.．]\s*([^。；\n]{2,42}?中毒)(?=\s|。|$)/g
const BRACKET_HEADING = /【([^】\n]{1,40})】/g

const GENERIC_TOPIC_TITLES = new Set([
  '急性中毒',
  '慢性中毒',
  '生产中毒',
  '使用中毒',
  '生活中毒',
  '职业中毒',
  '食物中毒',
])

const IMPORTANT_TERMS = [
  '是指', '主要', '表现', '诊断', '首选', '特效', '治疗', '机制',
  '抑制', '导致', '应', '需', '可', '常见', '分为', '死亡', '预后',
  '呼吸衰竭', '意识障碍', '解毒', '禁忌', '注意', '毒性',
]

const LOW_VALUE_TERMS = [
  '世纪', '截至', '我国于', '年开始', '年生产', '开发', '图9-', '表9-',
  '如图', '见表', '作者', '研究发现', '近年来', '结构式', '取代基',
  '烷基',
]

const LOW_INFORMATION_PATTERNS = [
  /(?:诊断)?依据如下[。；：:]?$/,
  /(?:主要)?表现如下[。；：:]?$/,
  /(?:常见)?原因如下[。；：:]?$/,
  /(?:具体)?分类如下[。；：:]?$/,
  /^详见表/,
]

function chineseNumber(value: string): number {
  if (CHINESE_NUMBERS[value]) return CHINESE_NUMBERS[value]
  if (value === '十一') return 11
  if (value === '十二') return 12
  return 0
}

function isTopicTitle(title: string): boolean {
  const value = title.replace(/\s+/g, '')
  if (!value || GENERIC_TOPIC_TITLES.has(value)) return false
  if (/诊断|治疗|病因|临床|检查|机制|预防|分级|分型/.test(value)) return false
  return true
}

function findTopicMarkers(content: string): TopicMarker[] {
  const candidates: TopicMarker[] = []
  TOPIC_HEADING.lastIndex = 0

  for (const match of content.matchAll(TOPIC_HEADING)) {
    const order = chineseNumber(match[1])
    const title = match[2].replace(/\s+/g, '').trim()
    if (!order || !isTopicTitle(title)) continue

    const leadingWhitespace = match[0].length - match[0].trimStart().length
    const index = (match.index ?? 0) + leadingWhitespace
    candidates.push({
      index,
      end: index + match[0].trimStart().length,
      order,
      title,
    })
  }

  const firstIndex = candidates.findIndex(marker => marker.order === 1)
  if (firstIndex < 0) return []

  const sequence: TopicMarker[] = []
  let expected = 1
  for (const marker of candidates.slice(firstIndex)) {
    if (marker.order !== expected) continue
    sequence.push(marker)
    expected += 1
  }

  return sequence.length >= 2 ? sequence : []
}

function canonicalSectionTitle(title: string): string {
  const value = title.replace(/\s+/g, '').replace(/[：:]+$/, '')

  if (/临床.*诊断|诊断.*临床/.test(value)) return '临床与诊断'
  if (/诊断.*鉴别|鉴别.*诊断/.test(value)) return '诊断与鉴别'
  if (/病因.*机制|机制.*病因/.test(value)) return '病因与机制'
  if (/机制.*解救|解救.*机制/.test(value)) return '机制与解救'
  if (/吸收.*代谢|毒物代谢/.test(value)) return '吸收与代谢'
  if (/分类/.test(value)) return '分类'
  if (/流行病学/.test(value)) return '流行病学'
  if (/病因/.test(value)) return '病因'
  if (/发病机制|中毒机制/.test(value)) return '发病机制'
  if (/病理生理/.test(value)) return '病理生理'
  if (/病理/.test(value)) return '病理'
  if (/临床表现|症状|体征/.test(value)) return '临床表现'
  if (/实验室检查/.test(value)) return '实验室检查'
  if (/影像/.test(value)) return '影像学检查'
  if (/辅助检查|检查/.test(value)) return '辅助检查'
  if (/鉴别诊断/.test(value)) return '鉴别诊断'
  if (/诊断/.test(value)) return '诊断'
  if (/治疗/.test(value)) return '治疗'
  if (/预防/.test(value)) return '预防'
  if (/预后/.test(value)) return '预后'
  if (/并发症/.test(value)) return '并发症'
  if (/定义|概述/.test(value)) return '核心概念'

  return value.length > 16 ? `${value.slice(0, 16)}…` : value
}

function cleanDigestText(content: string): string {
  return content
    .replace(/\r/g, '')
    .replace(/\n?\s*第[一二三四五六七八九十百零〇\d]+章\s+.{1,30}?\s+\d{1,4}\s*/g, ' ')
    .replace(/\n?\s*\d{1,4}\s+第[一二三四五六七八九十百零〇\d]+篇\s+[\u4e00-\u9fff]{2,18}\s*/g, ' ')
    .replace(/第[一二三四五六七八九十百零〇\d]+节\s*[|｜]\s*[\u4e00-\u9fff]{2,24}/g, ' ')
    .replace(/图\s*\d+(?:-\d+)+[^\n。]{0,28}/g, ' ')
    .replace(/（[A-Za-z][^）\n]{0,80}）/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function compactCjkSpacing(content: string): string {
  let value = content
  for (let index = 0; index < 3; index += 1) {
    value = value.replace(/([\u4e00-\u9fff])\s+([\u4e00-\u9fff])/g, '$1$2')
  }
  return value
}

function stripHistoricalClauses(content: string): string {
  const clauses = content
    .split(/[，；]/)
    .map(clause => clause.trim())
    .filter(Boolean)
  const useful = clauses.filter(clause => (
    !/(?:18|19|20)\d{2}\s*年|20\s*世纪|截至|进入中国|停止生产|禁止生产|禁止销售/.test(clause)
  ))
  return useful.join('，')
}

function shorten(text: string, maxLength = 78): string {
  const value = compactCjkSpacing(stripHistoricalClauses(cleanDigestText(text)))
    .replace(/^需要注意的是[，,]?/, '注意：')
    .replace(/^值得注意的是[，,]?/, '注意：')
    .replace(/。[：:]/g, '：')
    .trim()

  if (value.length <= maxLength) return value

  const window = value.slice(0, maxLength)
  const breakAt = Math.max(
    window.lastIndexOf('；'),
    window.lastIndexOf('，'),
    window.lastIndexOf('、')
  )
  const end = breakAt >= 48 ? breakAt : maxLength
  return `${window.slice(0, end).replace(/[，；、\s]+$/, '')}…`
}

function firstMeaningfulSentence(content: string): string {
  const cleaned = cleanDigestText(content)
  const sentences = cleaned
    .split(/(?<=[。！？；])\s*/)
    .map(sentence => sentence.trim())
    .filter(sentence => sentence.length >= 8 && !/^(图|表)\s*\d/.test(sentence))

  return shorten(sentences[0] || cleaned)
}

function normalizedForCompare(text: string): string {
  return text
    .toLowerCase()
    .replace(/核心说明|要点\d*/g, '')
    .replace(/[\s，。；：、“”‘’（）()【】,.!?;:'"-]/g, '')
}

function bigramSimilarity(left: string, right: string): number {
  const a = normalizedForCompare(left)
  const b = normalizedForCompare(right)
  if (!a || !b) return 0
  if (a.includes(b) || b.includes(a)) {
    return Math.min(a.length, b.length) / Math.max(a.length, b.length)
  }

  const aPairs = new Set<string>()
  const bPairs = new Set<string>()
  for (let index = 0; index < a.length - 1; index += 1) aPairs.add(a.slice(index, index + 2))
  for (let index = 0; index < b.length - 1; index += 1) bPairs.add(b.slice(index, index + 2))

  let intersection = 0
  for (const pair of aPairs) {
    if (bPairs.has(pair)) intersection += 1
  }
  const union = new Set([...aPairs, ...bPairs]).size
  return union ? intersection / union : 0
}

function dedupePoints(points: string[]): string[] {
  const result: string[] = []
  for (const point of points) {
    const value = shorten(point)
    if (value.length < 6) continue
    const duplicate = result.some(existing => bigramSimilarity(existing, value) >= 0.68)
    if (!duplicate) result.push(value)
  }
  return result
}

function candidateScore(text: string, hasTitle: boolean): number {
  let score = hasTitle ? 3 : 0
  for (const term of IMPORTANT_TERMS) {
    if (text.includes(term)) score += 1
  }
  for (const term of LOW_VALUE_TERMS) {
    if (text.includes(term)) score -= 3
  }
  if (/\d|%|mg|mmHg|ChE|AChE|CT|MRI/.test(text)) score += 0.5
  if (text.length >= 18 && text.length <= 120) score += 1
  if (text.length < 10) score -= 2
  if (LOW_INFORMATION_PATTERNS.some(pattern => pattern.test(text.trim()))) score -= 8
  return score
}

export function extractDigestPoints(content: string, maxPoints = 4): string[] {
  const cleaned = cleanDigestText(content)
  if (!cleaned) return []

  const parsed = parseContentPoints(cleaned)
  const candidates = parsed.map((point, index) => {
    const title = point.title
      .replace(/^核心说明(?:\s*·\s*\d+)?$/, '')
      .replace(/^要点\s*\d+$/, '')
      .replace(/\s*·\s*\d+$/, '')
      .trim()
    const body = firstMeaningfulSentence(point.body)
    let text = body

    if (title && body) {
      const normalizedTitle = normalizedForCompare(title)
      const normalizedBody = normalizedForCompare(body)
      text = normalizedBody.startsWith(normalizedTitle)
        ? body
        : `${title}：${body}`
    } else if (title) {
      text = title
    }

    const introBonus = point.level === 0 ? 3 : 0
    return {
      index,
      text: shorten(text),
      score: candidateScore(text, !!title) + introBonus,
    }
  }).filter(candidate => candidate.text.length >= 6 && candidate.score > 0)

  if (candidates.length <= 1) {
    const sentenceCandidates = cleaned
      .split(/(?<=[。！？；])\s*/)
      .map((sentence, index) => ({
        index,
        text: shorten(sentence),
        score: candidateScore(sentence, false),
      }))
      .filter(candidate => candidate.text.length >= 8 && candidate.score > 0)
    candidates.push(...sentenceCandidates)
  }

  const ranked = [...candidates]
    .sort((left, right) => right.score - left.score || left.index - right.index)
    .slice(0, Math.max(maxPoints * 2, maxPoints))
    .sort((left, right) => left.index - right.index)

  return dedupePoints(ranked.map(candidate => candidate.text)).slice(0, maxPoints)
}

function mergeSections(sections: RawKnowledgeSection[]): KnowledgeSection[] {
  const merged = new Map<string, string[]>()

  for (const section of sections) {
    const title = canonicalSectionTitle(section.title)
    const content = section.content.trim()
    if (!title || content.length < 8) continue

    const values = merged.get(title) || []
    const normalized = normalizedForCompare(content)
    const duplicate = values.some(existing => normalizedForCompare(existing) === normalized)
    if (!duplicate) values.push(content)
    merged.set(title, values)
  }

  return [...merged.entries()].map(([title, contents]) => {
    const content = contents.join('\n')
    const digestContent = prepareDigestContent(title, content)
    return {
      title,
      content,
      digest: extractDigestPoints(digestContent, title === '核心概念' ? 2 : 4),
    }
  }).filter(section => section.digest.length > 0)
}

function prepareDigestContent(title: string, content: string): string {
  const tablePattern = /表\s*\d+(?:-\d+)+\s*/g
  const matches = [...content.matchAll(tablePattern)]
  if (matches.length === 0) return content

  const keywords = title.includes('治疗')
    ? ['治疗', '疗法', '解毒']
    : title.includes('诊断')
      ? ['诊断', '鉴别']
      : title.includes('临床')
        ? ['临床', '症状', '体征']
        : [title]

  const segments: string[] = []
  const prose = content.slice(0, matches[0].index).trim()
  if (prose.length >= 20) segments.push(prose)

  matches.forEach((match, index) => {
    const start = match.index ?? 0
    const end = index + 1 < matches.length
      ? (matches[index + 1].index ?? content.length)
      : content.length
    const segment = content.slice(start, end)
    const heading = segment.slice(0, 80)
    if (keywords.some(keyword => heading.includes(keyword))) {
      segments.push(segment)
    }
  })

  return segments.join('\n') || prose || content
}

function parseBracketSections(content: string): RawKnowledgeSection[] {
  BRACKET_HEADING.lastIndex = 0
  const matches = [...content.matchAll(BRACKET_HEADING)]
  if (matches.length === 0) {
    return [{ title: '核心概念', content: content.trim() }]
  }

  const sections: RawKnowledgeSection[] = []
  const intro = content.slice(0, matches[0].index).trim()
  if (intro.length >= 12) {
    sections.push({ title: '核心概念', content: intro })
  }

  matches.forEach((match, index) => {
    const start = (match.index ?? 0) + match[0].length
    const end = index + 1 < matches.length
      ? (matches[index + 1].index ?? content.length)
      : content.length
    const sectionContent = content.slice(start, end).trim()
    if (sectionContent.length >= 8) {
      sections.push({
        title: canonicalSectionTitle(match[1]),
        content: sectionContent,
      })
    }
  })

  return sections
}

export function buildKnowledgeOutline(
  content: string,
  structuredSections: RawKnowledgeSection[] = []
): KnowledgeOutline {
  const topicMarkers = findTopicMarkers(content)

  if (topicMarkers.length >= 2) {
    const overviewContent = content.slice(0, topicMarkers[0].index).trim()
    const groups = topicMarkers.map((marker, index) => {
      const end = index + 1 < topicMarkers.length
        ? topicMarkers[index + 1].index
        : content.length
      const topicContent = content.slice(marker.end, end).trim()
      return {
        title: marker.title,
        sections: mergeSections(parseBracketSections(topicContent)),
      }
    }).filter(group => group.sections.length > 0)

    return {
      grouped: groups.length >= 2,
      overview: extractDigestPoints(overviewContent, 2),
      groups,
    }
  }

  const sourceSections = structuredSections.length > 0
    ? structuredSections
    : parseBracketSections(content)
  const sections = mergeSections(sourceSections)

  return {
    grouped: false,
    overview: [],
    groups: sections.length > 0 ? [{ title: '', sections }] : [],
  }
}

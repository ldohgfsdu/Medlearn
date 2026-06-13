export interface ContentPoint {
  marker: string
  title: string
  body: string
  level: number
}

const MARKER_SOURCE = [
  '【[^】\\n]{1,30}】',
  '[一二三四五六七八九十百]+[、.．]',
  '[（(][一二三四五六七八九十百]+[）)]',
  '[（(]\\d{1,2}[）)]',
  '\\d{1,2}[.．、](?!\\d)',
  '[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]',
  '\\d{1,2}[）)]',
].join('|')

const MARKER_AT_START = new RegExp(`^(${MARKER_SOURCE})\\s*`)
const MARKER_BOUNDARY = new RegExp(`(^|[\\s。！？；：:])(${MARKER_SOURCE})\\s*`, 'gm')

const BODY_STARTERS = [
  '是', '为', '指', '包括', '主要', '常见', '最', '可', '用于', '通过',
  '由于', '在', '当', '若', '表现', '目的', '应', '需', '建议', '推荐',
  '一般', '其', '该', '本', '凡', '对', '有', '由', '采用', '首选',
  '适用于', '临床', '病人', '患者', '大多数', '少数', '目前', '近年来',
  '通常', '根据', '分为', '以',
]

function markerLevel(marker: string): number {
  if (marker.startsWith('【')) return 1
  if (/^[一二三四五六七八九十百]+[、.．]$/.test(marker)) return 1
  if (/^[（(][一二三四五六七八九十百]+[）)]$/.test(marker)) return 2
  if (/^\d{1,2}[.．、]$/.test(marker)) return 2
  if (/^[（(]\d{1,2}[）)]$/.test(marker)) return 3
  if (/^\d{1,2}[）)]$/.test(marker)) return 3
  return 4
}

function cleanText(content: string): string {
  return content
    .replace(/\r/g, '')
    .replace(/\n\s*第[一二三四五六七八九十百零〇\d]+章\s+.{1,36}?\s+\d{1,4}\s+(?=[A-Za-z（(【\u4e00-\u9fff])/g, '\n')
    .replace(/\n\s*\d{1,4}\s+第[一二三四五六七八九十百零〇\d]+篇\s+[\u4e00-\u9fff]{2,16}\s+/g, '\n')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function splitTitleAndBody(rest: string): { title: string; body: string } {
  const value = rest.trim().replace(/^[：:]\s*/, '')
  if (!value) return { title: '', body: '' }

  const colonIndex = value.search(/[：:]/)
  const colonPrefix = colonIndex > 0 ? value.slice(0, colonIndex).trim() : ''
  if (
    colonIndex > 0
    && colonIndex <= 42
    && !/[，。！？；]/.test(colonPrefix)
    && (colonPrefix.length <= 24 || !/\s/.test(colonPrefix))
  ) {
    return {
      title: value.slice(0, colonIndex).trim(),
      body: value.slice(colonIndex + 1).trim(),
    }
  }

  const whitespace = [...value.matchAll(/\s+/g)]
  for (const match of whitespace) {
    const index = match.index ?? 0
    if (index < 1 || index > 36) continue
    const remainder = value.slice(index).trim()
    if (BODY_STARTERS.some(starter => remainder.startsWith(starter))) {
      return {
        title: value.slice(0, index).trim(),
        body: remainder,
      }
    }
  }

  if (value.length <= 42 && !/[，。！？；：:]/.test(value)) {
    return { title: value, body: '' }
  }

  const firstSpace = value.search(/\s/)
  if (firstSpace > 0 && firstSpace <= 18) {
    return {
      title: value.slice(0, firstSpace).trim(),
      body: value.slice(firstSpace).trim(),
    }
  }

  const clauseEnd = value.search(/[，。；]/)
  if (clauseEnd > 1 && clauseEnd <= 36) {
    return {
      title: value.slice(0, clauseEnd).trim(),
      body: value.slice(clauseEnd + 1).trim(),
    }
  }

  return { title: '', body: value }
}

function splitLongBody(body: string, maxChars = 420): string[] {
  const value = body.trim()
  if (value.length <= maxChars) return value ? [value] : []

  const sentences = value
    .split(/(?<=[。！？；])\s*/)
    .map(sentence => sentence.trim())
    .filter(Boolean)

  if (sentences.length <= 1) {
    const chunks: string[] = []
    for (let start = 0; start < value.length; start += maxChars) {
      chunks.push(value.slice(start, start + maxChars).trim())
    }
    return chunks.filter(Boolean)
  }

  const chunks: string[] = []
  let current = ''
  for (const sentence of sentences) {
    const candidate = `${current}${sentence}`.trim()
    if (current && candidate.length > maxChars) {
      chunks.push(current)
      current = sentence
    } else {
      current = candidate
    }
  }
  if (current) chunks.push(current)
  return chunks
}

function expandLongPoints(points: ContentPoint[]): ContentPoint[] {
  const expanded: ContentPoint[] = []

  for (const point of points) {
    const chunks = splitLongBody(point.body)
    if (chunks.length <= 1) {
      expanded.push(point)
      continue
    }

    chunks.forEach((body, index) => {
      expanded.push({
        ...point,
        marker: index === 0 ? point.marker : '',
        title: point.title
          ? `${point.title}${index === 0 ? '' : ` · ${index + 1}`}`
          : `要点 ${String(index + 1).padStart(2, '0')}`,
        body,
      })
    })
  }

  return expanded
}

export function parseContentPoints(content: string): ContentPoint[] {
  const cleaned = cleanText(content)
  if (!cleaned) return []

  const normalized = cleaned.replace(
    MARKER_BOUNDARY,
    (_match, boundary: string, marker: string) => `${boundary.trim() ? boundary : ''}\n${marker} `
  )

  const points: ContentPoint[] = []
  let current: ContentPoint | null = null
  let intro = ''

  const flushCurrent = () => {
    if (!current) return
    current.body = current.body.trim()
    if (current.title || current.body) points.push(current)
    current = null
  }

  for (const rawLine of normalized.split(/\n+/)) {
    const line = rawLine.trim()
    if (!line) continue

    const markerMatch = line.match(MARKER_AT_START)
    if (!markerMatch) {
      if (current) {
        current.body = `${current.body}\n${line}`.trim()
      } else {
        intro = `${intro}\n${line}`.trim()
      }
      continue
    }

    flushCurrent()
    const marker = markerMatch[1]
    const rest = line.slice(markerMatch[0].length).trim()

    if (marker.startsWith('【')) {
      current = {
        marker,
        title: marker.slice(1, -1).trim(),
        body: rest.replace(/^[：:]\s*/, ''),
        level: markerLevel(marker),
      }
      continue
    }

    const { title, body } = splitTitleAndBody(rest)
    current = {
      marker,
      title,
      body,
      level: markerLevel(marker),
    }
  }

  flushCurrent()

  const introPoints = splitLongBody(intro).map((body, index) => ({
    marker: '',
    title: points.length > 0
      ? (index === 0 ? '核心说明' : `核心说明 · ${index + 1}`)
      : `要点 ${String(index + 1).padStart(2, '0')}`,
    body,
    level: 0,
  }))

  return expandLongPoints([...introPoints, ...points])
}

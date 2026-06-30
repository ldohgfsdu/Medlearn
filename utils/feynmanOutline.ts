import {
  buildKnowledgeOutline,
  extractDigestPoints,
  type RawKnowledgeSection,
} from './knowledgeOutline'

const DISEASE_PROMPTS = ['定义与本质', '发病机制', '临床表现', '诊断要点', '治疗原则']
const DRUG_PROMPTS = ['药理作用', '适应证', '禁忌与不良反应', '用法用量']
const DEFAULT_PROMPTS = ['核心定义', '关键机制', '临床意义', '常见误区']

export interface FeynmanScaffold {
  intro: string
  mustCover: string[]
  keyReminders: string[]
  tips: string[]
}

function normalizeNodeType(type?: string | null): string {
  return (type || '').trim().toLowerCase()
}

function pickMustCover(
  type: string,
  sectionTitles: string[],
): string[] {
  if (sectionTitles.length >= 3) {
    return sectionTitles.slice(0, 6)
  }

  if (type === 'disease' || type === '疾病') {
    return DISEASE_PROMPTS
  }

  if (type === 'drug' || type === '药物') {
    return DRUG_PROMPTS
  }

  return DEFAULT_PROMPTS
}

export function buildFeynmanScaffold(params: {
  title: string
  type?: string | null
  content?: string | null
  keyPoints?: string[] | null
  structuredSections?: RawKnowledgeSection[]
}): FeynmanScaffold {
  const content = params.content || ''
  const structuredSections = params.structuredSections || []
  const outline = buildKnowledgeOutline(content, structuredSections)
  const rawSectionTitles = structuredSections
    .map((section) => section.title.trim())
    .filter((title) => title.length > 0)
  const outlineSectionTitles = outline.groups.flatMap((group) =>
    group.sections.map((section) => section.title),
  )
  const sectionTitles =
    rawSectionTitles.length >= 3 ? rawSectionTitles : outlineSectionTitles
  const nodeType = normalizeNodeType(params.type)
  const storedPoints = (params.keyPoints || []).filter(
    (point): point is string => typeof point === 'string' && point.trim().length > 0,
  )
  const keyReminders = storedPoints.length > 0
    ? extractDigestPoints(storedPoints.join('。'), 3)
    : outline.overview.length > 0
      ? outline.overview
      : extractDigestPoints(content, 2)

  return {
    intro: `向一位低年级同学口头讲解「${params.title}」，建议 2–3 分钟，不要照读原文。`,
    mustCover: pickMustCover(nodeType, sectionTitles),
    keyReminders,
    tips: [
      '先讲「是什么」，再讲「为什么」，最后讲「临床上怎么用」',
      '用因果链串联，不要只背名词',
      '故意举一个典型临床场景收尾',
    ],
  }
}
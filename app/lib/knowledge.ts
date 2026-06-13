import { getSupabase } from './supabase'

/**
 * Knowledge access layer aligned to the authoritative knowledge_nodes schema.
 */

type KnowledgeNodeRow = {
  id: string
  title: string
  type: string
  content: string | null
  subject: string | null
  chapter: string | null
  sub_chapter: string | null
  key_points: string[] | null
  related_nodes: string[] | null
  textbook: string | null
  edition: string | null
  updated_at: string
}

export type KnowledgePoint = {
  id: string
  title: string
  type: 'disease' | 'drug' | 'test' | 'concept' | 'symptom'
  content: Record<string, unknown>
  relations: {
    target_id: string
    target_title: string
    relation_type: string
    strength: number
  }[]
  metadata: {
    source: {
      book: string
      edition: string
      page?: number
      chapter: string
    }
    last_updated: string
    evidence_level?: string
    confidence: number
  }
  aliases?: string[]
  definition?: { content?: string } | string
  mechanism?: string
  clinical_relevance?: string
}

export type SearchOptions = {
  type?: string[]
  chapter?: string
  limit?: number
  include_relations?: boolean
}

function mapNodeType(type: string): KnowledgePoint['type'] {
  if (type === 'disease' || type === 'drug' || type === 'test' || type === 'symptom') {
    return type
  }
  return 'concept'
}

function mapNodeToKnowledgePoint(row: KnowledgeNodeRow): KnowledgePoint {
  return {
    id: row.id,
    title: row.title,
    type: mapNodeType(row.type),
    content: row.content ? { body: row.content } : {},
    relations: (row.related_nodes ?? []).map((targetId) => ({
      target_id: targetId,
      target_title: targetId,
      relation_type: 'related',
      strength: 0.5,
    })),
    metadata: {
      source: {
        book: row.textbook || row.subject || '未知教材',
        edition: row.edition || '',
        chapter: row.chapter || row.sub_chapter || '未分类',
      },
      last_updated: row.updated_at,
      confidence: 0.8,
    },
    aliases: row.key_points ?? [],
    definition: row.content ?? undefined,
  }
}

export const knowledge = {
  async get_knowledge_point(id: string): Promise<KnowledgePoint | null> {
    const supabase = getSupabase()
    if (!supabase) return null

    const { data, error } = await supabase
      .from('knowledge_nodes')
      .select(
        'id,title,type,content,subject,chapter,sub_chapter,key_points,related_nodes,textbook,edition,updated_at',
      )
      .eq('id', id)
      .maybeSingle()

    if (error || !data) return null
    return mapNodeToKnowledgePoint(data as KnowledgeNodeRow)
  },

  async search(query: string, options: SearchOptions = {}): Promise<KnowledgePoint[]> {
    const supabase = getSupabase()
    if (!supabase) return []

    let queryBuilder = supabase
      .from('knowledge_nodes')
      .select(
        'id,title,type,content,subject,chapter,sub_chapter,key_points,related_nodes,textbook,edition,updated_at',
      )
      .limit(options.limit || 20)

    if (query.trim()) {
      const pattern = `%${query.trim()}%`
      queryBuilder = queryBuilder.or(`title.ilike.${pattern},content.ilike.${pattern}`)
    }

    if (options.type && options.type.length > 0) {
      queryBuilder = queryBuilder.in('type', options.type)
    }

    if (options.chapter) {
      queryBuilder = queryBuilder.eq('chapter', options.chapter)
    }

    const { data, error } = await queryBuilder
    if (error || !data) return []

    return (data as KnowledgeNodeRow[]).map(mapNodeToKnowledgePoint)
  },

  async get_chapter_tree(): Promise<Record<string, { id: string; title: string; type: string }[]>> {
    const supabase = getSupabase()
    if (!supabase) return {}

    const { data, error } = await supabase
      .from('knowledge_nodes')
      .select('id,title,type,chapter,sub_chapter')
      .order('chapter')
      .order('title')

    if (error || !data) return {}

    const tree: Record<string, { id: string; title: string; type: string }[]> = {}
    for (const item of data) {
      const chapter = item.chapter || item.sub_chapter || '未分类'
      if (!tree[chapter]) tree[chapter] = []
      tree[chapter].push({
        id: item.id,
        title: item.title,
        type: item.type,
      })
    }

    return tree
  },

  async compare(ids: string[]): Promise<{
    points: KnowledgePoint[]
    common_fields: string[]
    differences: Record<string, unknown>
  }> {
    const points = (await Promise.all(ids.map((id) => this.get_knowledge_point(id)))).filter(
      (point): point is KnowledgePoint => point !== null,
    )

    return {
      points,
      common_fields: [],
      differences: {},
    }
  },
}

export const getKnowledgePoint = knowledge.get_knowledge_point.bind(knowledge)
export const searchKnowledge = knowledge.search.bind(knowledge)
export const getChapterTree = knowledge.get_chapter_tree.bind(knowledge)

export default knowledge
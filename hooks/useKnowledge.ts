import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import { calculateLearningRecordStats } from '@/utils/learningRecords'
import {
  buildSubjectCatalog,
  buildSubjectOrFilter,
  getChapterSortWeight,
  type SubjectCatalogEntry,
} from '@/utils/knowledgeCatalog'

export interface KnowledgeNodeSummary {
  id: string
  title: string
  type: string
  subject?: string | null
  chapter?: string | null
  sub_chapter?: string | null
  level?: number | null
  order_num?: number | null
  node_source?: string | null
}

export interface ChapterSection {
  name: string
  nodes: KnowledgeNodeSummary[]
  chapters: ChapterGroup[]
}

export interface ChapterGroup {
  name: string
  nodes: KnowledgeNodeSummary[]
}

function isMissingTableError(error: { code?: string; message?: string } | null): boolean {
  if (!error) return false
  return error.code === 'PGRST205' || error.message?.includes('Could not find the table') === true
}

export function useKnowledgeNode(id: string) {
  return useQuery({
    queryKey: ['knowledgeNode', id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('*')
        .eq('id', id)
        .single()

      if (error) throw error
      return data
    },
    enabled: !!id,
  })
}

export function useRelatedChunks(nodeId: string) {
  return useQuery({
    queryKey: ['relatedChunks', nodeId],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('document_chunks')
        .select('content, page_number, chapter, section')
        .eq('related_node_id', nodeId)
        .order('page_number', { ascending: true })
        .limit(6)

      if (error) throw error
      return data ?? []
    },
    enabled: !!nodeId,
    staleTime: 300_000,
  })
}

export function useCausalChain(nodeId: string) {
  return useQuery({
    queryKey: ['causalChain', nodeId],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('causal_chains')
        .select('*')
        .contains('related_nodes', [nodeId])
        .limit(1)
        .maybeSingle()

      if (error) throw error
      return data
    },
    enabled: !!nodeId,
  })
}

export function useSubjectCatalog() {
  return useQuery({
    queryKey: ['subjectCatalog'],
    queryFn: async (): Promise<SubjectCatalogEntry[]> => {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('subject,textbook')

      if (error) throw error
      return buildSubjectCatalog(data ?? [])
    },
    staleTime: 300_000,
  })
}

/** @deprecated Prefer useSubjectCatalog for counts and labels. */
export function useSubjects() {
  const query = useSubjectCatalog()
  return {
    ...query,
    data: query.data?.map((entry) => entry.name),
  }
}

export function useKnowledgeLibraryStats() {
  return useQuery({
    queryKey: ['knowledgeLibraryStats'],
    queryFn: async () => {
      const [nodesResult, subjectsResult] = await Promise.all([
        supabase.from('knowledge_nodes').select('*', { count: 'exact', head: true }),
        supabase.from('knowledge_nodes').select('subject,textbook'),
      ])

      if (nodesResult.error) throw nodesResult.error
      if (subjectsResult.error) throw subjectsResult.error

      const subjects = buildSubjectCatalog(subjectsResult.data ?? [])
      return {
        totalNodes: nodesResult.count ?? 0,
        subjectCount: subjects.length,
        subjects,
      }
    },
    staleTime: 300_000,
  })
}

export function useTreeBySubject(subject: string) {
  return useQuery({
    queryKey: ['tree', subject],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('id, title, type, subject, chapter, sub_chapter, level, order_num, node_source')
        .or(buildSubjectOrFilter(subject))
        .order('order_num', { ascending: true })

      if (error) throw error

      const partMap = new Map<string, KnowledgeNodeSummary[]>()
      for (const node of data ?? []) {
        const partName = node.chapter || '基础/概论'
        const bucket = partMap.get(partName) ?? []
        bucket.push(node)
        partMap.set(partName, bucket)
      }

      const tree: ChapterSection[] = []

      for (const [partName, nodes] of partMap) {
        const chapterMap = new Map<string, KnowledgeNodeSummary[]>()
        const standaloneNodes: KnowledgeNodeSummary[] = []

        for (const node of nodes) {
          if (node.sub_chapter) {
            const bucket = chapterMap.get(node.sub_chapter) ?? []
            bucket.push(node)
            chapterMap.set(node.sub_chapter, bucket)
          } else {
            standaloneNodes.push(node)
          }
        }

        const chapters: ChapterGroup[] = Array.from(chapterMap.entries())
          .map(([name, chapterNodes]) => ({
            name,
            nodes: chapterNodes.filter((node) => node.level !== 2),
          }))
          .filter((chapter) => chapter.nodes.length > 0)
          .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))

        tree.push({ name: partName, nodes: standaloneNodes, chapters })
      }

      return tree.sort((a, b) => getChapterSortWeight(a.name) - getChapterSortWeight(b.name))
    },
    enabled: !!subject,
  })
}

export function useSearchNodes(query: string, subject?: string) {
  const trimmed = query.trim()

  return useQuery({
    queryKey: ['searchNodes', trimmed, subject ?? 'all'],
    queryFn: async () => {
      const escaped = trimmed.replace(/[%_,.()]/g, '')
      const pattern = escaped.toLowerCase()

      if (subject) {
        const { data, error } = await supabase
          .from('knowledge_nodes')
          .select('id, title, type, subject, chapter, sub_chapter')
          .or(buildSubjectOrFilter(subject))
          .limit(1000)

        if (error) throw error

        return (data ?? [])
          .filter((node) => (
            node.title?.toLowerCase().includes(pattern)
            || node.sub_chapter?.toLowerCase().includes(pattern)
          ))
          .slice(0, 30)
      }

      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('id, title, type, subject, chapter, sub_chapter')
        .or(`title.ilike.%${escaped}%,sub_chapter.ilike.%${escaped}%`)
        .limit(30)

      if (error) throw error
      return data ?? []
    },
    enabled: trimmed.length >= 2,
  })
}

interface HomeStats {
  completedToday: number
  learningDays: number
  completedCases: number
}

interface RecentSession {
  id: string
  title: string
  completedAt: string | null
}

export function useHomeStats(userId: string | undefined) {
  return useQuery({
    queryKey: ['homeStats', userId],
    queryFn: async (): Promise<HomeStats> => {
      const sessionsResult = await supabase
        .from('case_sessions')
        .select('completed_at')
        .eq('user_id', userId!)
        .eq('status', 'completed')

      if (sessionsResult.error) {
        if (isMissingTableError(sessionsResult.error)) {
          return { completedToday: 0, learningDays: 0, completedCases: 0 }
        }
        throw sessionsResult.error
      }

      const sessions = sessionsResult.data ?? []
      const recordStats = calculateLearningRecordStats(sessions)

      return {
        ...recordStats,
        completedCases: sessions.length,
      }
    },
    enabled: !!userId,
    staleTime: 60_000,
  })
}

export function useRecentSessions(userId: string | undefined) {
  return useQuery({
    queryKey: ['recentSessions', userId],
    queryFn: async (): Promise<RecentSession[]> => {
      const { data, error } = await supabase
        .from('case_sessions')
        .select('id, completed_at, case_templates(title)')
        .eq('user_id', userId!)
        .eq('status', 'completed')
        .order('completed_at', { ascending: false })
        .limit(3)

      if (error) {
        if (isMissingTableError(error)) return []
        throw error
      }

      return (data ?? []).map((session) => {
        const template = session.case_templates as { title?: string } | null
        return {
          id: session.id,
          title: template?.title || '病例复盘',
          completedAt: session.completed_at,
        }
      })
    },
    enabled: !!userId,
    staleTime: 60_000,
  })
}
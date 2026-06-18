import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'

export interface DiseaseKnowledgeNode {
  id: string
  title: string
  display_title?: string | null
  aspect?: string | null
  raw_aspect?: string | null
  content?: string | null
  key_points?: string[] | null
  structured_sections?: { title?: string; content?: string }[] | null
  order_num?: number | null
  chapter_section_id: string
  source_span?: {
    evidence?: string | null
    evidence_items?: string[] | null
    page_start?: number | null
    page_end?: number | null
    provenance?: {
      page_start?: number | null
      page_end?: number | null
    } | null
  } | null
}

export function useDiseaseDetail(diseaseId: string) {
  return useQuery({
    queryKey: ['diseaseDetail', diseaseId],
    queryFn: async () => {
      const entityResult = await supabase
        .from('disease_entities')
        .select('*')
        .eq('disease_id', diseaseId)
        .eq('resolution_status', 'confirmed')
        .eq('node_type', 'disease')
        .maybeSingle()

      if (entityResult.error) throw entityResult.error
      if (!entityResult.data) return null
      if (entityResult.data.content_status !== 'available') {
        return {
          entity: entityResult.data,
          nodes: [] as DiseaseKnowledgeNode[],
          sections: [],
          chain: null,
        }
      }

      const [nodesResult, chainsResult] = await Promise.all([
        supabase
          .from('knowledge_nodes')
          .select('id, title, display_title, aspect, raw_aspect, content, key_points, structured_sections, order_num, chapter_section_id, source_span')
          .eq('disease_id', diseaseId)
          .eq('content_class', 'confirmed_disease')
          .order('order_num', { ascending: true }),
        supabase
          .from('causal_chains')
          .select('*')
          .eq('disease_id', diseaseId)
          .eq('validation_status', 'valid')
          .order('created_at', { ascending: false })
          .limit(1),
      ])

      if (nodesResult.error) throw nodesResult.error
      if (chainsResult.error) throw chainsResult.error

      const sectionIds = [...new Set(
        (nodesResult.data ?? [])
          .map((node) => node.chapter_section_id)
          .filter(Boolean),
      )]
      const sectionsResult = sectionIds.length
        ? await supabase
            .from('chapter_sections')
            .select('chapter_section_id, catalog_path, display_title')
            .in('chapter_section_id', sectionIds)
        : { data: [], error: null }

      if (sectionsResult.error) throw sectionsResult.error

      return {
        entity: entityResult.data,
        nodes: (nodesResult.data ?? []) as DiseaseKnowledgeNode[],
        sections: sectionsResult.data ?? [],
        chain: chainsResult.data?.[0] ?? null,
      }
    },
    enabled: !!diseaseId,
  })
}

export function useChapterKnowledge(chapterSectionId: string) {
  return useQuery({
    queryKey: ['chapterKnowledge', chapterSectionId],
    queryFn: async () => {
      const [sectionResult, nodesResult] = await Promise.all([
        supabase
          .from('chapter_sections')
          .select('*')
          .eq('chapter_section_id', chapterSectionId)
          .maybeSingle(),
        supabase
          .from('knowledge_nodes')
          .select('id, title, display_title, aspect, raw_aspect, content, key_points, structured_sections, order_num, disease_id, content_class')
          .eq('chapter_section_id', chapterSectionId)
          .eq('content_class', 'non_disease_knowledge')
          .order('order_num', { ascending: true }),
      ])

      if (sectionResult.error) throw sectionResult.error
      if (nodesResult.error) throw nodesResult.error
      if (!sectionResult.data) return null

      return { section: sectionResult.data, nodes: nodesResult.data ?? [] }
    },
    enabled: !!chapterSectionId,
  })
}

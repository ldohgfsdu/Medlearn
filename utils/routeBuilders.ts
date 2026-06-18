import type { Href } from 'expo-router'
import type {
  CatalogNodeType,
  ContentStatus,
  KnowledgeContentClass,
} from '@/utils/knowledgeIdentity'

export type DiseaseDetailTab = 'knowledge' | 'reasoning' | 'training'

export interface KnowledgeNavigationNode {
  content_class?: KnowledgeContentClass | null
  node_type?: CatalogNodeType | null
  content_status?: ContentStatus | null
  disease_id?: string | null
  chapter_section_id?: string | null
  overview_slug?: string | null
  search_aspect?: string | null
}

export function buildDiseaseRoute(
  diseaseId: string,
  tab: DiseaseDetailTab = 'knowledge',
  aspect?: string | null,
): Href {
  return {
    pathname: '/disease/[id]',
    params: { id: diseaseId, tab, ...(aspect ? { aspect } : {}) },
  } as unknown as Href
}

export function buildChapterRoute(chapterSectionId: string): Href {
  return {
    pathname: '/chapter/[id]',
    params: { id: chapterSectionId },
  } as unknown as Href
}

export function buildOverviewRoute(slug: string): Href {
  return {
    pathname: '/overview/[slug]',
    params: { slug },
  } as unknown as Href
}

export function resolveTarget(node: KnowledgeNavigationNode): Href | null {
  if (
    node.content_class === 'confirmed_disease'
    && node.node_type === 'disease'
    && node.content_status === 'available'
    && node.disease_id
  ) {
    return buildDiseaseRoute(node.disease_id, 'knowledge', node.search_aspect)
  }

  if (node.content_class === 'non_disease_knowledge' && node.chapter_section_id) {
    return buildChapterRoute(node.chapter_section_id)
  }

  return null
}

export function resolveCatalogTarget(node: KnowledgeNavigationNode): Href | null {
  if (node.node_type === 'overview' && node.overview_slug) {
    return buildOverviewRoute(node.overview_slug)
  }
  const availableTarget = resolveTarget(node)
  if (availableTarget) return availableTarget

  if (
    node.content_class === 'confirmed_disease'
    && node.node_type === 'disease'
    && node.disease_id
  ) {
    return buildDiseaseRoute(node.disease_id, 'knowledge', node.search_aspect)
  }

  return null
}

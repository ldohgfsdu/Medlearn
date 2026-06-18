export const HYBRID_SEARCH_MAX_QUERY_LENGTH = 100

export function escapeIlikePattern(query: string): string {
  return query
    .slice(0, HYBRID_SEARCH_MAX_QUERY_LENGTH)
    .replace(/\\/g, '\\\\')
    .replace(/%/g, '\\%')
    .replace(/_/g, '\\_')
    .replace(/[,().]/g, '')
}
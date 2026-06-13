import { useQuery } from '@tanstack/react-query'
import { generateLearningPath, getNextRecommendedNode, type LearningPath } from '@/services/learning-path'

export function useLearningPath(userId: string | undefined, subject: string) {
  return useQuery({
    queryKey: ['learningPath', userId, subject],
    queryFn: () => generateLearningPath(userId!, subject),
    enabled: !!userId && !!subject,
    staleTime: 60_000, // 1分钟缓存
  })
}

export function useNextRecommended(userId: string | undefined, subject: string) {
  const { data: path, ...rest } = useLearningPath(userId, subject)
  return {
    data: path ? getNextRecommendedNode(path) : null,
    path,
    ...rest,
  }
}

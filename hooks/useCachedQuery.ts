import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import { cacheService } from '@/services/cache'

/**
 * 带离线缓存的 Query Hook
 * 策略：
 * 1. 有网络时：正常请求，成功后写入缓存
 * 2. 无网络时：从缓存读取数据
 * 3. 网络恢复时：自动刷新
 */
export function useCachedQuery<T>(
  queryKey: string[],
  queryFn: () => Promise<T>,
  options?: {
    enabled?: boolean
    staleTime?: number
    cacheExpiryMs?: number
  }
) {
  const cacheKey = queryKey.join(':')

  return useQuery({
    queryKey,
    queryFn: async () => {
      try {
        const data = await queryFn()
        // 成功后写入缓存
        await cacheService.set(cacheKey, data, options?.cacheExpiryMs)
        return data
      } catch (error) {
        // 请求失败，尝试从缓存读取
        const cached = await cacheService.get<T>(cacheKey)
        if (cached !== null) {
          return cached
        }
        throw error
      }
    },
    enabled: options?.enabled,
    staleTime: options?.staleTime ?? 60_000,
  })
}

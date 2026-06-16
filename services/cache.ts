import AsyncStorage from '@react-native-async-storage/async-storage'

const CACHE_PREFIX = '@medlearn_cache:'
const CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000 // 默认24小时过期
const MAX_ENTRIES = 500

interface CacheEntry<T> {
  data: T
  timestamp: number
  expiryMs: number
}

/** Simple mutex to prevent concurrent eviction */
let evictionLock = false
const pendingEvictions: Array<() => void> = []

async function withEvictionLock(fn: () => Promise<void>): Promise<void> {
  if (evictionLock) {
    await new Promise<void>(resolve => pendingEvictions.push(resolve))
  }
  evictionLock = true
  try {
    await fn()
  } finally {
    evictionLock = false
    const next = pendingEvictions.shift()
    if (next) next()
  }
}

/**
 * 通用缓存服务
 * 使用 AsyncStorage 存储数据，支持 TTL 过期
 */
export const cacheService = {
  /**
   * 写入缓存
   */
  async set<T>(key: string, data: T, expiryMs: number = CACHE_EXPIRY_MS): Promise<void> {
    try {
      // Check and evict under lock to prevent race conditions
      await withEvictionLock(async () => {
        const keys = await AsyncStorage.getAllKeys()
        const cacheKeys = keys.filter(k => k.startsWith(CACHE_PREFIX))
        if (cacheKeys.length >= MAX_ENTRIES) {
          // Evict oldest entries (target half to reduce frequency of eviction)
          const targetSize = Math.floor(MAX_ENTRIES * 0.8)
          const toEvict = cacheKeys.length - targetSize
          if (toEvict > 0) {
            // Only load entries we need to sort, evict oldest by key order as approximation
            // (true LRU would require updating timestamps on read, too expensive)
            await AsyncStorage.multiRemove(cacheKeys.slice(0, toEvict))
          }
        }
      })

      const entry: CacheEntry<T> = {
        data,
        timestamp: Date.now(),
        expiryMs,
      }
      await AsyncStorage.setItem(
        CACHE_PREFIX + key,
        JSON.stringify(entry)
      )
    } catch (error) {
      // Cache write failure should not break the app
      console.warn('[cache] Failed to write:', error)
    }
  },

  /**
   * 读取缓存
   * 返回 null 表示缓存不存在或已过期
   */
  async get<T>(key: string): Promise<T | null> {
    try {
      const raw = await AsyncStorage.getItem(CACHE_PREFIX + key)
      if (!raw) return null

      const entry: CacheEntry<T> = JSON.parse(raw)
      if (Date.now() - entry.timestamp > entry.expiryMs) {
        await AsyncStorage.removeItem(CACHE_PREFIX + key).catch(() => {})
        return null
      }
      return entry.data
    } catch {
      return null
    }
  },

  /**
   * 删除缓存
   */
  async remove(key: string): Promise<void> {
    try {
      await AsyncStorage.removeItem(CACHE_PREFIX + key)
    } catch (error) {
      console.warn('[cache] Failed to remove:', error)
    }
  },

  /**
   * 清空所有缓存
   */
  async clear(): Promise<void> {
    try {
      const keys = await AsyncStorage.getAllKeys()
      const cacheKeys = keys.filter(k => k.startsWith(CACHE_PREFIX))
      await AsyncStorage.multiRemove(cacheKeys)
    } catch (error) {
      console.warn('[cache] Failed to clear:', error)
    }
  },

  /**
   * 获取缓存大小（条目数）
   */
  async size(): Promise<number> {
    try {
      const keys = await AsyncStorage.getAllKeys()
      return keys.filter(k => k.startsWith(CACHE_PREFIX)).length
    } catch {
      return 0
    }
  },
}

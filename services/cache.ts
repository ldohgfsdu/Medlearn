import AsyncStorage from '@react-native-async-storage/async-storage'

const CACHE_PREFIX = '@medlearn_cache:'
const CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000 // 默认24小时过期
const MAX_ENTRIES = 500

interface CacheEntry<T> {
  data: T
  timestamp: number
  expiryMs: number
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
    // 检查缓存条目数，超出限制时删除最旧的条目
    const keys = await AsyncStorage.getAllKeys()
    const cacheKeys = keys.filter(k => k.startsWith(CACHE_PREFIX))
    if (cacheKeys.length >= MAX_ENTRIES) {
      const entries: { key: string; timestamp: number }[] = []
      const pairs = await AsyncStorage.multiGet(cacheKeys)
      for (const [k, v] of pairs) {
        if (v) {
          try {
            const parsed = JSON.parse(v)
            entries.push({ key: k, timestamp: parsed.timestamp ?? 0 })
          } catch {
            entries.push({ key: k, timestamp: 0 })
          }
        }
      }
      entries.sort((a, b) => a.timestamp - b.timestamp)
      const toRemove = entries.slice(0, entries.length - MAX_ENTRIES + 1).map(e => e.key)
      if (toRemove.length > 0) {
        await AsyncStorage.multiRemove(toRemove)
      }
    }

    const entry: CacheEntry<T> = {
      data,
      timestamp: Date.now(),
      expiryMs,
    }
    await AsyncStorage.setItem(
      CACHE_PREFIX + key,
      JSON.stringify(entry)
    )
  },

  /**
   * 读取缓存
   * 返回 null 表示缓存不存在或已过期
   */
  async get<T>(key: string): Promise<T | null> {
    const raw = await AsyncStorage.getItem(CACHE_PREFIX + key)
    if (!raw) return null

    try {
      const entry: CacheEntry<T> = JSON.parse(raw)
      if (Date.now() - entry.timestamp > entry.expiryMs) {
        await AsyncStorage.removeItem(CACHE_PREFIX + key)
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
    await AsyncStorage.removeItem(CACHE_PREFIX + key)
  },

  /**
   * 清空所有缓存
   */
  async clear(): Promise<void> {
    const keys = await AsyncStorage.getAllKeys()
    const cacheKeys = keys.filter(k => k.startsWith(CACHE_PREFIX))
    await AsyncStorage.multiRemove(cacheKeys)
  },

  /**
   * 获取缓存大小（条目数）
   */
  async size(): Promise<number> {
    const keys = await AsyncStorage.getAllKeys()
    return keys.filter(k => k.startsWith(CACHE_PREFIX)).length
  },
}

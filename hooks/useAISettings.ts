import { useCallback, useEffect, useState } from 'react'
import {
  DEFAULT_AI_SETTINGS,
  invalidateAISettingsCache,
  isCustomChatReady,
  loadAISettings,
  resetAISettings,
  saveAISettings,
  usesCustomChatProvider,
  type AISettings,
} from '@/lib/ai-settings'
import { testChatConnection } from '@/services/ai-runtime'

export function useAISettings() {
  const [settings, setSettings] = useState<AISettings>(DEFAULT_AI_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    invalidateAISettingsCache()
    const loaded = await loadAISettings()
    setSettings(loaded)
    setLoading(false)
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const save = useCallback(async (next: AISettings) => {
    setSaving(true)
    setTestResult(null)
    try {
      const saved = await saveAISettings(next)
      setSettings(saved)
      return saved
    } finally {
      setSaving(false)
    }
  }, [])

  const reset = useCallback(async () => {
    setSaving(true)
    setTestResult(null)
    try {
      const restored = await resetAISettings()
      setSettings(restored)
      return restored
    } finally {
      setSaving(false)
    }
  }, [])

  const testConnection = useCallback(async (draft?: AISettings) => {
    setTesting(true)
    setTestResult(null)
    try {
      const target = draft ?? settings
      const message = await testChatConnection(target)
      setTestResult(message)
      return message
    } catch (error) {
      const message = error instanceof Error ? error.message : '连接测试失败'
      setTestResult(message)
      throw error
    } finally {
      setTesting(false)
    }
  }, [settings])

  return {
    settings,
    loading,
    saving,
    testing,
    testResult,
    save,
    reset,
    refresh,
    testConnection,
    usesCustom: usesCustomChatProvider(settings),
    isCustomReady: isCustomChatReady(settings),
  }
}
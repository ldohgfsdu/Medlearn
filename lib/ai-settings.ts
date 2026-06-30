import AsyncStorage from '@react-native-async-storage/async-storage'
import { Platform } from 'react-native'

export type AIProviderPreset = 'server' | 'deepseek' | 'openai' | 'custom'
export type EmbeddingProvider = 'ollama' | 'proxy'

export interface AISettings {
  /** 对话提供方：server=走 Medlearn 服务端代理 */
  provider: AIProviderPreset
  chatApiKey: string
  chatBaseUrl: string
  chatModel: string
  embeddingProvider: EmbeddingProvider
  ollamaUrl: string
  ollamaEmbedModel: string
}

export interface AIOverride {
  api_key: string
  base_url: string
  model: string
}

const STORAGE_KEY = '@medlearn/ai-settings/v1'

const DEFAULT_OLLAMA_URL =
  process.env.EXPO_PUBLIC_OLLAMA_URL?.replace(/\/$/, '') || 'http://127.0.0.1:11434'
const DEFAULT_OLLAMA_MODEL = process.env.EXPO_PUBLIC_OLLAMA_EMBED_MODEL || 'bge-m3'
const DEFAULT_EMBED_PROVIDER =
  (process.env.EXPO_PUBLIC_EMBEDDING_PROVIDER as EmbeddingProvider | undefined) || 'ollama'

export const AI_PROVIDER_PRESETS: Record<
  Exclude<AIProviderPreset, 'server' | 'custom'>,
  Pick<AISettings, 'chatBaseUrl' | 'chatModel'>
> = {
  deepseek: {
    chatBaseUrl: 'https://api.deepseek.com/v1',
    chatModel: 'deepseek-chat',
  },
  openai: {
    chatBaseUrl: 'https://api.openai.com/v1',
    chatModel: 'gpt-4o-mini',
  },
}

export const DEFAULT_AI_SETTINGS: AISettings = {
  provider: 'server',
  chatApiKey: '',
  chatBaseUrl: AI_PROVIDER_PRESETS.deepseek.chatBaseUrl,
  chatModel: AI_PROVIDER_PRESETS.deepseek.chatModel,
  embeddingProvider: DEFAULT_EMBED_PROVIDER,
  ollamaUrl: DEFAULT_OLLAMA_URL,
  ollamaEmbedModel: DEFAULT_OLLAMA_MODEL,
}

function normalizeUrl(url: string, fallback: string): string {
  const trimmed = url.trim()
  if (!trimmed) return fallback
  return trimmed.replace(/\/$/, '')
}

export function normalizeAISettings(raw: Partial<AISettings> | null | undefined): AISettings {
  const provider = raw?.provider ?? DEFAULT_AI_SETTINGS.provider
  const preset =
    provider === 'deepseek' || provider === 'openai' ? AI_PROVIDER_PRESETS[provider] : null

  return {
    provider,
    chatApiKey: typeof raw?.chatApiKey === 'string' ? raw.chatApiKey.trim() : '',
    chatBaseUrl: normalizeUrl(
      raw?.chatBaseUrl ?? preset?.chatBaseUrl ?? DEFAULT_AI_SETTINGS.chatBaseUrl,
      DEFAULT_AI_SETTINGS.chatBaseUrl,
    ),
    chatModel:
      typeof raw?.chatModel === 'string' && raw.chatModel.trim()
        ? raw.chatModel.trim()
        : preset?.chatModel ?? DEFAULT_AI_SETTINGS.chatModel,
    embeddingProvider:
      raw?.embeddingProvider === 'proxy' || raw?.embeddingProvider === 'ollama'
        ? raw.embeddingProvider
        : DEFAULT_AI_SETTINGS.embeddingProvider,
    ollamaUrl: normalizeUrl(raw?.ollamaUrl ?? DEFAULT_AI_SETTINGS.ollamaUrl, DEFAULT_OLLAMA_URL),
    ollamaEmbedModel:
      typeof raw?.ollamaEmbedModel === 'string' && raw.ollamaEmbedModel.trim()
        ? raw.ollamaEmbedModel.trim()
        : DEFAULT_OLLAMA_MODEL,
  }
}

export function usesCustomChatProvider(settings: AISettings): boolean {
  return settings.provider !== 'server'
}

export function isCustomChatReady(settings: AISettings): boolean {
  if (!usesCustomChatProvider(settings)) return true
  return Boolean(settings.chatApiKey && settings.chatBaseUrl && settings.chatModel)
}

export function buildAIOverride(settings: AISettings): AIOverride | null {
  if (!usesCustomChatProvider(settings) || !isCustomChatReady(settings)) return null
  return {
    api_key: settings.chatApiKey,
    base_url: settings.chatBaseUrl,
    model: settings.chatModel,
  }
}

let cachedSettings: AISettings | null = null

export async function loadAISettings(): Promise<AISettings> {
  if (cachedSettings) return cachedSettings

  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY)
    if (!raw) {
      cachedSettings = { ...DEFAULT_AI_SETTINGS }
      return cachedSettings
    }
    cachedSettings = normalizeAISettings(JSON.parse(raw) as Partial<AISettings>)
    return cachedSettings
  } catch {
    cachedSettings = { ...DEFAULT_AI_SETTINGS }
    return cachedSettings
  }
}

export async function saveAISettings(next: AISettings): Promise<AISettings> {
  const normalized = normalizeAISettings(next)
  cachedSettings = normalized
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(normalized))
  return normalized
}

export async function resetAISettings(): Promise<AISettings> {
  cachedSettings = { ...DEFAULT_AI_SETTINGS }
  await AsyncStorage.removeItem(STORAGE_KEY)
  return cachedSettings
}

export function invalidateAISettingsCache(): void {
  cachedSettings = null
}

/** Web 调试时可从 localStorage 直接读取，与 AsyncStorage 同源 */
export function getAISettingsStorageLabel(): string {
  return Platform.OS === 'web' ? '浏览器本地存储' : '设备本地存储'
}
import { supabase } from '@/lib/supabase'
import {
  buildAIOverride,
  isCustomChatReady,
  loadAISettings,
  usesCustomChatProvider,
  type AISettings,
} from '@/lib/ai-settings'

export interface AIMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface AIResponse {
  choices?: Array<{ message?: { content?: string } }>
}

interface InvokeOptions {
  temperature?: number
  maxTokens?: number
  responseFormat?: { type: 'json_object' }
  onSlowResponse?: () => void
}

async function invokeViaProxy(
  messages: AIMessage[],
  options: InvokeOptions,
  aiOverride: ReturnType<typeof buildAIOverride>,
): Promise<AIResponse> {
  const warningId = options.onSlowResponse
    ? setTimeout(options.onSlowResponse, 15_000)
    : null
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  try {
    const request = supabase.functions.invoke<AIResponse>('ai-proxy', {
      body: {
        messages,
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens ?? 2_000,
        response_format: options.responseFormat,
        ...(aiOverride ? { ai_override: aiOverride } : {}),
      },
    })
    const timeout = new Promise<never>((_, reject) => {
      timeoutId = setTimeout(() => reject(new Error('AI_REQUEST_TIMEOUT')), 30_000)
    })
    const { data, error } = await Promise.race([request, timeout])

    if (error) throw new Error(`AI_PROXY_ERROR: ${error.message}`)
    if (!data) throw new Error('AI_EMPTY_RESPONSE')
    return data
  } finally {
    if (warningId) clearTimeout(warningId)
    if (timeoutId) clearTimeout(timeoutId)
  }
}

async function invokeDirect(
  settings: AISettings,
  messages: AIMessage[],
  options: InvokeOptions,
): Promise<AIResponse> {
  if (!isCustomChatReady(settings)) {
    throw new Error('请先在「AI 设置」中填写 API Key、接口地址和模型名称')
  }

  const warningId = options.onSlowResponse
    ? setTimeout(options.onSlowResponse, 15_000)
    : null
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  try {
    const request = fetch(`${settings.chatBaseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${settings.chatApiKey}`,
      },
      body: JSON.stringify({
        model: settings.chatModel,
        messages,
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens ?? 2_000,
        ...(options.responseFormat?.type === 'json_object'
          ? { response_format: options.responseFormat }
          : {}),
      }),
    })

    const timeout = new Promise<never>((_, reject) => {
      timeoutId = setTimeout(() => reject(new Error('AI_REQUEST_TIMEOUT')), 30_000)
    })

    const response = (await Promise.race([request, timeout])) as Response
    if (!response.ok) {
      const detail = await response.text().catch(() => '')
      throw new Error(`AI_API_ERROR: HTTP ${response.status}${detail ? ` · ${detail.slice(0, 120)}` : ''}`)
    }

    const data = (await response.json()) as AIResponse
    if (!data) throw new Error('AI_EMPTY_RESPONSE')
    return data
  } finally {
    if (warningId) clearTimeout(warningId)
    if (timeoutId) clearTimeout(timeoutId)
  }
}

export async function invokeChatCompletion(
  messages: AIMessage[],
  options: InvokeOptions = {},
  settingsOverride?: AISettings,
): Promise<AIResponse> {
  const settings = settingsOverride ?? (await loadAISettings())

  if (usesCustomChatProvider(settings)) {
    return invokeDirect(settings, messages, options)
  }

  return invokeViaProxy(messages, options, null)
}

export async function testChatConnection(settings: AISettings): Promise<string> {
  const result = await invokeChatCompletion(
    [
      { role: 'system', content: '你是连接测试助手，只回复“连接成功”四个字。' },
      { role: 'user', content: 'ping' },
    ],
    { temperature: 0, maxTokens: 16 },
    settings,
  )

  const content = result.choices?.[0]?.message?.content?.trim()
  if (!content) throw new Error('模型未返回内容')
  return `连接成功：${content.slice(0, 40)}`
}

export async function getCasePatientAIOverride() {
  const settings = await loadAISettings()
  return buildAIOverride(settings)
}
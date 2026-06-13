import { matchDocuments, supabase } from '@/lib/supabase'
import { getEmbedding } from './vector'

interface AIMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

interface AIResponse {
  choices?: Array<{ message?: { content?: string } }>
}

interface ContextChunk {
  document_name?: string | null
  page_number?: number | null
  content: string
}

async function invokeAI(
  messages: AIMessage[],
  options: {
    temperature?: number
    maxTokens?: number
    responseFormat?: { type: 'json_object' }
    onSlowResponse?: () => void
  } = {}
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

function extractJSON(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    const match = text.match(/\{[\s\S]*\}/)
    if (!match) throw new Error('AI 返回内容不包含有效 JSON')

    try {
      return JSON.parse(match[0])
    } catch {
      throw new Error('无法解析 AI 返回的 JSON')
    }
  }
}

export interface EvaluationResult {
  score: number
  feedback: string
  missingPoints: string[]
  reference: string
}

/**
 * 通用医学学习对话（非严格 RAG 评估场景）
 * 始终通过 ai-proxy，服务端密钥隔离。
 * 提示模型保持教育用途、建议用户在费曼/病例中深入练习。
 */
export async function sendChatMessage(
  history: AIMessage[],
  onSlowResponse?: () => void
): Promise<string> {
  const result = await invokeAI(
    [
      {
        role: 'system',
        content:
          '你是 Medlearn 的医学学习助手。仅用于教育和复习目的。回答要准确、结构化，优先引用常见教材概念。不要给出针对真实患者的个性化诊断或治疗建议。回答末尾可简要建议用户通过“费曼复述”或“病例训练”进一步练习相关知识点。',
      },
      ...history,
    ],
    {
      temperature: 0.4,
      maxTokens: 2000,
      onSlowResponse,
    },
  )

  const content = result.choices?.[0]?.message?.content
  if (!content) throw new Error('AI_EMPTY_CONTENT')
  return content.trim()
}

export async function evaluateWithRAG(
  nodeTitle: string,
  userTranscript: string,
  onSlowResponse?: () => void
): Promise<EvaluationResult> {
  const vector = await getEmbedding(userTranscript)
  const contextChunks = (await matchDocuments(vector, 3)) as ContextChunk[]

  if (!contextChunks || contextChunks.length === 0) {
    throw new Error('TEXTBOOK_NOT_FOUND')
  }

  const textbookContext = contextChunks
    .map(
      (chunk) =>
        `【教材：${chunk.document_name || '参考资料'} 第${chunk.page_number || '?'}页】 ${chunk.content}`,
    )
    .join('\n\n')

  const result = await invokeAI(
    [
      {
        role: 'system',
        content:
          '你是严谨的医学教师。只能依据用户提供的教材原文评估复述，必须输出 JSON，不得补充教材之外的医学结论。',
      },
      {
        role: 'user',
        content: `知识点：${nodeTitle}

【教材原文】
${textbookContext}

【学生复述】
${userTranscript}

请返回：{"score": 0-100, "feedback": "...", "missingPoints": ["..."], "reference": "..."}`,
      },
    ],
    {
      temperature: 0.2,
      responseFormat: { type: 'json_object' },
      onSlowResponse,
    },
  )

  const content = result.choices?.[0]?.message?.content
  if (!content) throw new Error('AI_EMPTY_CONTENT')

  const parsed = extractJSON(content) as Partial<EvaluationResult>
  return {
    score: typeof parsed.score === 'number' ? parsed.score : 0,
    feedback: typeof parsed.feedback === 'string' ? parsed.feedback : '无法解析反馈',
    missingPoints: Array.isArray(parsed.missingPoints)
      ? parsed.missingPoints.filter((point): point is string => typeof point === 'string')
      : [],
    reference:
      typeof parsed.reference === 'string'
        ? parsed.reference
        : contextChunks[0]?.document_name || '参考教材',
  }
}

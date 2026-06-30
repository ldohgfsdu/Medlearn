import { matchDocuments } from '@/lib/supabase'
import { getEmbedding } from './vector'
import { invokeChatCompletion, type AIMessage } from './ai-runtime'
import {
  buildFeynmanEvaluationUserPrompt,
  FEYNMAN_EVALUATION_SYSTEM_PROMPT,
} from './feynman-prompt'

interface ContextChunk {
  document_name?: string | null
  page_number?: number | null
  content: string
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
  strengths?: string[]
  nextSentence?: string
}

export interface EvaluateWithRAGOptions {
  nodeId?: string
  attempt?: number
}

export type { AIMessage }

/**
 * 通用医学学习对话（非严格 RAG 评估场景）
 * 默认走 ai-proxy；若在「AI 设置」中配置了自有 Key，则直连对应模型。
 */
export async function sendChatMessage(
  history: AIMessage[],
  onSlowResponse?: () => void
): Promise<string> {
  const result = await invokeChatCompletion(
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
  onSlowResponse?: () => void,
  options?: EvaluateWithRAGOptions,
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

  const result = await invokeChatCompletion(
    [
      {
        role: 'system',
        content: FEYNMAN_EVALUATION_SYSTEM_PROMPT,
      },
      {
        role: 'user',
        content: buildFeynmanEvaluationUserPrompt({
          nodeTitle,
          textbookContext,
          userTranscript,
          attempt: options?.attempt,
        }),
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
    strengths: Array.isArray(parsed.strengths)
      ? parsed.strengths.filter((point): point is string => typeof point === 'string')
      : [],
    nextSentence:
      typeof parsed.nextSentence === 'string' ? parsed.nextSentence : undefined,
    reference:
      typeof parsed.reference === 'string'
        ? parsed.reference
        : contextChunks[0]?.document_name || '参考教材',
  }
}
import { matchDocuments } from '@/lib/supabase'
import { getEmbedding } from './vector'

const API_KEY = process.env.EXPO_PUBLIC_AI_API_KEY || ''
const BASE_URL = process.env.EXPO_PUBLIC_AI_API_BASE_URL || 'https://token-plan-cn.xiaomimimo.com/v1'
const MODEL = process.env.EXPO_PUBLIC_AI_MODEL || 'mimo-v2.5-pro'

export interface EvaluationResult {
  score: number
  feedback: string
  missingPoints: string[]
  reference: string
}

/**
 * RAG 驱动的费曼复述评估引擎
 */
export async function evaluateWithRAG(nodeTitle: string, userTranscript: string): Promise<EvaluationResult> {
  // 1. 获取复述的向量
  const vector = await getEmbedding(userTranscript)

  // 2. 去数据库找最相关的 2 段教材原文
  const contextChunks = await matchDocuments(vector, 2)
  const textbookContext = contextChunks.map((c: any) => `【教材页码 ${c.page_number}】: ${c.content}`).join('\n\n')

  // 3. 构建 Prompt
  const systemPrompt = `你是一名严谨的医学教授。你将根据提供的教材原文，对学生的费曼复述进行评估。
不要使用你自带的知识，必须以提供的【教材原文】为准。`

  const userPrompt = `
知识点标题：${nodeTitle}

【教材原文】：
${textbookContext || '（未找到相关教材片段，请根据通用医学知识评估）'}

【学生复述内容】：
${userTranscript}

请严格按以下 JSON 格式评估：
{
  "score": 0-100的数字,
  "feedback": "简短的专业反馈",
  "missingPoints": ["漏掉的教材关键点1", "点2"],
  "reference": "引用的教材名称及页码"
}`

  // 4. 调用 AI API
  const response = await fetch(`${BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`
    },
    body: JSON.stringify({
      model: MODEL,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      response_format: { type: 'json_object' }
    })
  })

  const result = await response.json()
  const evaluation = JSON.parse(result.choices[0].message.content)

  return {
    score: evaluation.score,
    feedback: evaluation.feedback,
    missingPoints: evaluation.missingPoints,
    reference: evaluation.reference || (contextChunks[0]?.document_name || '参考教材')
  }
}

import { supabase } from '@/lib/supabase'

export interface ExamQuestion {
  id: string
  type: 'single' | 'multiple'
  question: string
  options: string[]
  answer: number       // 正确答案索引（single）或位掩码（multiple）
  explanation: string
  related_nodes: string[]
  difficulty: number
}

export interface ExamSession {
  id: string
  questionIds: string[]
  currentQuestionIndex: number
  answers: Record<number, number>  // questionIndex -> answer
  score: number
  startedAt: string
}

/**
 * AI 生成考试题目
 */
export async function generateExamQuestions(
  nodeIds: string[],
  count: number = 10,
  difficulty: number = 2
): Promise<ExamQuestion[]> {
  // 获取知识点信息
  const { data: nodes } = await supabase
    .from('knowledge_nodes')
    .select('id, title, content, key_points')
    .in('id', nodeIds)

  if (!nodes || nodes.length === 0) {
    throw new Error('未找到知识点')
  }

  const knowledgeContext = nodes.map(n =>
    `【${n.title}】${n.content || ''}${n.key_points ? '\n关键要点：' + (n.key_points as string[]).join('；') : ''}`
  ).join('\n\n')

  const prompt = `你是一名医学考试出题专家。根据以下医学知识点内容，生成 ${count} 道选择题。

要求：
1. 难度级别：${difficulty}（1=简单，2=中等，3=困难）
2. 包含单选题和多选题（约7:3比例）
3. 每题4个选项，单选题1个正确答案，多选题2-3个正确答案
4. 选项要有迷惑性但不能有歧义
5. 必须提供详细解析

知识点内容：
${knowledgeContext}

请严格按以下 JSON 格式返回：
{
  "questions": [
    {
      "type": "single",
      "question": "题目文本",
      "options": ["选项A", "选项B", "选项C", "选项D"],
      "answer": 0,
      "explanation": "解析文本",
      "difficulty": 2
    }
  ]
}

对于多选题，answer 为正确选项索引的位掩码（如选项0和2正确则为 0b0101 = 5）`

  const messages = [
    { role: 'system', content: '你是一名专业的医学考试出题专家，擅长根据教材内容生成高质量选择题。' },
    { role: 'user', content: prompt },
  ]

  const { data: result, error } = await supabase.functions.invoke('ai-proxy', {
    body: {
      messages,
      temperature: 0.5,
      max_tokens: 4096,
      response_format: { type: 'json_object' },
    },
  })
  if (error) throw new Error(`AI 代理请求失败: ${error.message}`)
  const content = result.choices?.[0]?.message?.content
  if (!content) throw new Error('AI 返回内容为空')

  let parsed
  try {
    parsed = JSON.parse(content)
  } catch {
    throw new Error('AI 返回的 JSON 格式无效')
  }

  const questions: ExamQuestion[] = (parsed.questions || []).map((q: any, i: number) => ({
    id: `${Date.now()}-${i}-${Math.random().toString(36).slice(2)}`,
    type: q.type || 'single',
    question: q.question,
    options: q.options,
    answer: q.answer,
    explanation: q.explanation || '',
    related_nodes: nodeIds,
    difficulty: q.difficulty || difficulty,
  }))

  return questions
}

function popcount(n: number): number {
  let count = 0
  while (n > 0) {
    count += n & 1
    n >>>= 1
  }
  return count
}

/**
 * 计算答题得分
 */
export function calculateScore(
  questions: ExamQuestion[],
  answers: Record<number, number>
): { totalScore: number; correctCount: number; wrongQuestions: number[] } {
  let correctCount = 0
  const wrongQuestions: number[] = []

  questions.forEach((q, i) => {
    const userAnswer = answers[i]
    if (userAnswer === undefined) {
      wrongQuestions.push(i)
      return
    }

    if (q.type === 'single') {
      if (userAnswer === q.answer) {
        correctCount++
      } else {
        wrongQuestions.push(i)
      }
    } else {
      // 多选题：完全匹配得满分，部分正确得50%
      if (userAnswer === q.answer) {
        correctCount++
      } else {
        const correctBits = userAnswer & q.answer
        const incorrectBits = userAnswer & ~q.answer
        const totalBits = popcount(q.answer)
        const matchedBits = popcount(correctBits)
        if (totalBits > 0 && matchedBits > 0 && incorrectBits === 0) {
          correctCount += 0.5
        }
        wrongQuestions.push(i)
      }
    }
  })

  const totalScore = questions.length > 0
    ? Math.round((correctCount / questions.length) * 100)
    : 0

  return { totalScore, correctCount, wrongQuestions }
}

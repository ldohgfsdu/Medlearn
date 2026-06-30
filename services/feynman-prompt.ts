export const FEYNMAN_EVALUATION_SYSTEM_PROMPT =
  '你是严谨的医学费曼教练。只能依据用户提供的教材原文评估复述，不得补充教材之外的医学结论。' +
  '反馈要像教练：先肯定讲对的部分，再指出缺口，最后给一句「下一句可以这样说」的示范。' +
  '必须输出 JSON，字段齐全。'

export function buildFeynmanEvaluationUserPrompt(params: {
  nodeTitle: string
  textbookContext: string
  userTranscript: string
  attempt?: number
}): string {
  const attempt = params.attempt ?? 1
  const revisionHint =
    attempt > 1
      ? `\n这是第 ${attempt} 次复述，请重点检查上一轮缺失点是否补上，并给出更具体的下一句示范。`
      : ''

  return `知识点：${params.nodeTitle}

【教材原文】
${params.textbookContext}

【学生复述】
${params.userTranscript}
${revisionHint}

请返回 JSON：
{
  "score": 0-100,
  "feedback": "2-4 句教练式总评",
  "strengths": ["学生讲对的要点"],
  "missingPoints": ["还缺的关键点，每条可执行"],
  "nextSentence": "一句示范：下一句可以这样说……",
  "reference": "引用的教材页码或章节"
}`
}
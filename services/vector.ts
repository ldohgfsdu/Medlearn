/**
 * 向量生成服务
 * 将用户的复述文字转化为数字向量，用于 Supabase RAG 检索
 */
export async function getEmbedding(text: string): Promise<number[]> {
  const apiKey = process.env.EXPO_PUBLIC_SILICONFLOW_KEY || ''

  try {
    const response = await fetch('https://api.siliconflow.cn/v1/embeddings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'BAAI/bge-m3',
        input: text
      })
    })
    const result = await response.json()
    return result.data[0].embedding
  } catch (error) {
    console.error('向量生成失败:', error)
    throw new Error('无法理解复述内容，请检查网络')
  }
}

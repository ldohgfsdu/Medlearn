import { supabase } from '@/lib/supabase'

export interface LearningPathNode {
  id: string
  title: string
  type: string
  subject: string
  chapter: string
  mastery: number    // 0-100 掌握度
  status: 'locked' | 'available' | 'in_progress' | 'mastered'
}

export interface LearningPath {
  id: string
  title: string
  nodes: LearningPathNode[]
  progress: number   // 0-100 完成百分比
}

/**
 * 根据用户掌握度生成推荐学习路径
 * 策略：
 * 1. 获取用户在某个科目下所有知识点的掌握度（从 spaced_repetition 和 feynman_records 聚合）
 * 2. 按章节分组，按 order_num 排序
 * 3. 标记每个节点的状态：mastered(>=80), in_progress(>=40), available(前置已掌握), locked(前置未掌握)
 * 4. 推荐下一个应学习的知识点
 */
export async function generateLearningPath(
  userId: string,
  subject: string
): Promise<LearningPath> {
  // 获取该科目所有知识点
  const { data: nodes } = await supabase
    .from('knowledge_nodes')
    .select('id, title, type, subject, chapter, order_num, causal_links')
    .eq('subject', subject)
    .order('order_num', { ascending: true })

  if (!nodes || nodes.length === 0) {
    return { id: `path_${subject}`, title: `${subject}学习路径`, nodes: [], progress: 0 }
  }

  // 获取掌握度数据
  const [repetitionRes, feynmanRes] = await Promise.all([
    supabase
      .from('spaced_repetition')
      .select('node_id, last_quality, repetitions, ease_factor')
      .eq('user_id', userId),
    supabase
      .from('feynman_records')
      .select('node_id, ai_score')
      .eq('user_id', userId),
  ])

  // 聚合掌握度
  const masteryMap = new Map<string, number>()

  // 从 spaced_repetition 获取
  for (const r of (repetitionRes.data || [])) {
    const quality = r.last_quality || 0
    const reps = r.repetitions || 0
    // 质量越高、重复次数越多，掌握度越高
    const mastery = Math.min(100, Math.round((quality / 5) * 60 + (Math.min(reps, 5) / 5) * 40))
    masteryMap.set(r.node_id, mastery)
  }

  // 从 feynman_records 获取（取最高分）
  for (const f of (feynmanRes.data || [])) {
    const score = (f.ai_score as any)?.totalScore ?? (f.ai_score as any)?.accuracy ?? 0
    const existing = masteryMap.get(f.node_id) || 0
    masteryMap.set(f.node_id, Math.max(existing, score))
  }

  // 构建路径节点
  const pathNodes: LearningPathNode[] = nodes.map(node => {
    const mastery = masteryMap.get(node.id) || 0
    let status: LearningPathNode['status'] = 'available'

    if (mastery >= 80) {
      status = 'mastered'
    } else if (mastery >= 40) {
      status = 'in_progress'
    }

    return {
      id: node.id,
      title: node.title,
      type: node.type || 'concept',
      subject: node.subject,
      chapter: node.chapter || '',
      mastery,
      status,
    }
  })

  // 标记锁定节点：如果前一个同章节节点未掌握，则锁定
  let prevChapter = ''
  let prevMastered = true
  for (const node of pathNodes) {
    if (node.chapter !== prevChapter) {
      prevChapter = node.chapter
      prevMastered = true
    }

    if (node.status === 'mastered') {
      prevMastered = true
    } else if (!prevMastered && node.mastery < 20) {
      node.status = 'locked'
    } else {
      prevMastered = node.mastery >= 40
    }
  }

  // 计算总进度
  const masteredCount = pathNodes.filter(n => n.status === 'mastered').length
  const progress = pathNodes.length > 0
    ? Math.round((masteredCount / pathNodes.length) * 100)
    : 0

  return {
    id: `path_${subject}`,
    title: `${subject}学习路径`,
    nodes: pathNodes,
    progress,
  }
}

/**
 * 获取推荐学习的下一个知识点
 */
export function getNextRecommendedNode(path: LearningPath): LearningPathNode | null {
  // 优先推荐 in_progress 的
  const inProgress = path.nodes.find(n => n.status === 'in_progress')
  if (inProgress) return inProgress

  // 其次推荐 available 的
  const available = path.nodes.find(n => n.status === 'available')
  if (available) return available

  return null
}

/**
 * SM-2 间隔重复算法
 * 基于用户对知识点的掌握质量，计算下次复习时间和难度
 */

export interface RepetitionState {
  nodeId: string
  nextReview: string    // ISO date
  interval: number      // 天数
  easeFactor: number    // 难度因子 (>= 1.3)
  repetitions: number   // 成功重复次数
  lastQuality: number   // 上次评估质量 (0-5)
}

// 质量等级定义
// 5 - 完美掌握
// 4 - 犹豫后正确
// 3 - 困难但正确
// 2 - 错误但似曾相识
// 1 - 错误且陌生
// 0 - 完全不记得

export function calculateNextReview(
  current: Omit<RepetitionState, 'nextReview'>,
  quality: number
): RepetitionState {
  quality = Math.max(0, Math.min(5, quality))
  let { interval, easeFactor, repetitions } = current

  // 质量低于3，重置重复次数
  if (quality < 3) {
    repetitions = 0
    interval = 1
  } else {
    repetitions += 1
    if (repetitions === 1) {
      interval = 1
    } else if (repetitions === 2) {
      interval = 6
    } else {
      interval = Math.round(interval * easeFactor)
    }
  }

  // 更新难度因子
  easeFactor = Math.max(
    1.3,
    easeFactor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
  )

  const nextReview = new Date()
  nextReview.setDate(nextReview.getDate() + interval)

  return {
    nodeId: current.nodeId,
    nextReview: nextReview.toISOString(),
    interval,
    easeFactor,
    repetitions,
    lastQuality: quality,
  }
}

/**
 * 根据费曼评估分数 (0-100) 映射到 SM-2 质量等级 (0-5)
 */
export function scoreToQuality(score: number): number {
  if (score >= 90) return 5
  if (score >= 75) return 4
  if (score >= 60) return 3
  if (score >= 40) return 2
  if (score >= 20) return 1
  return 0
}

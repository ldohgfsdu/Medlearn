/**
 * 计算连续学习天数
 * 从今天或昨天开始往回数，遇到断天就停
 */
export function calcStreak(sessions: { completed_at: string | null }[]): number {
  if (sessions.length === 0) return 0

  const toLocalDate = (date: Date): string => {
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    const d = String(date.getDate()).padStart(2, '0')
    return `${y}-${m}-${d}`
  }

  const days = new Set(
    sessions
      .map((s) => s.completed_at ? toLocalDate(new Date(s.completed_at)) : null)
      .filter((d): d is string => !!d)
  )
  const sorted = Array.from(days).sort().reverse()
  const today = toLocalDate(new Date())
  const yesterday = toLocalDate(new Date(Date.now() - 86400000))

  // 连续天数从今天或昨天开始算
  if (sorted[0] !== today && sorted[0] !== yesterday) return 0

  let streak = 1
  for (let i = 0; i < sorted.length - 1; i++) {
    const curr = new Date(sorted[i])
    const prev = new Date(sorted[i + 1])
    const diff = (curr.getTime() - prev.getTime()) / 86400000
    if (diff === 1) {
      streak++
    } else {
      break
    }
  }
  return streak
}

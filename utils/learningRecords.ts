export interface CompletedLearningRecord {
  completed_at: string | null
}

export interface LearningRecordStats {
  completedToday: number
  learningDays: number
}

function toLocalDateKey(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Summarize completed work without rewarding or punishing consecutive days.
 * A day remains part of the learner's record even after a break.
 */
export function calculateLearningRecordStats(
  records: CompletedLearningRecord[],
  now = new Date()
): LearningRecordStats {
  const today = toLocalDateKey(now)
  const completedDates = records
    .map((record) => record.completed_at)
    .filter((completedAt): completedAt is string => !!completedAt)
    .map((completedAt) => toLocalDateKey(new Date(completedAt)))

  return {
    completedToday: completedDates.filter((date) => date === today).length,
    learningDays: new Set(completedDates).size,
  }
}

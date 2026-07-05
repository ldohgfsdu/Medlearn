import AsyncStorage from '@react-native-async-storage/async-storage'
import { getSectionDetail, getTextbookTree } from '@/services/textbookService'
import {
  locateWrongQuestionCandidates,
  type WrongQuestionCandidate,
} from '@/utils/wrongQuestionIntake'

const STORAGE_KEY = '@medlearn/wrong-question-records'

export type WrongQuestionMistakeReason =
  | 'concept_confusion'
  | 'missed_clue'
  | 'differential_error'
  | 'memory_gap'

export interface WrongQuestionReviewContext {
  correctAnswer?: string
  userAnswer?: string
  mistakeReason?: WrongQuestionMistakeReason | null
  updatedAt?: string | null
}

export interface WrongQuestionRecord {
  id: string
  question: string
  candidate: WrongQuestionCandidate
  createdAt: string
  reviewedAt?: string | null
  review?: WrongQuestionReviewContext
}

export async function locateWrongQuestion(question: string): Promise<WrongQuestionCandidate[]> {
  const tree = await getTextbookTree()
  const details = await Promise.all(
    tree.sections.map((section) => getSectionDetail(section.id)),
  )
  return locateWrongQuestionCandidates(
    question,
    details.filter((detail): detail is NonNullable<typeof detail> => detail != null),
  )
}

export async function loadWrongQuestionRecords(): Promise<WrongQuestionRecord[]> {
  const raw = await AsyncStorage.getItem(STORAGE_KEY)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed.filter(isWrongQuestionRecord) : []
  } catch {
    return []
  }
}

async function writeWrongQuestionRecords(records: WrongQuestionRecord[]): Promise<WrongQuestionRecord[]> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(records))
  return records
}

export async function saveWrongQuestionRecord(
  question: string,
  candidate: WrongQuestionCandidate,
): Promise<WrongQuestionRecord[]> {
  const current = await loadWrongQuestionRecords()
  const record: WrongQuestionRecord = {
    id: `${Date.now()}-${candidate.id}`,
    question: question.trim(),
    candidate,
    createdAt: new Date().toISOString(),
    reviewedAt: null,
    review: extractWrongQuestionReviewContext(question),
  }
  const next = [record, ...current.filter((item) => item.candidate.id !== candidate.id)].slice(0, 50)
  return writeWrongQuestionRecords(next)
}

export async function markWrongQuestionReviewed(recordId: string): Promise<WrongQuestionRecord[]> {
  const current = await loadWrongQuestionRecords()
  const next = current.map((record) => (
    record.id === recordId ? { ...record, reviewedAt: new Date().toISOString() } : record
  ))
  return writeWrongQuestionRecords(next)
}

export async function reactivateWrongQuestionRecord(recordId: string): Promise<WrongQuestionRecord[]> {
  const current = await loadWrongQuestionRecords()
  const next = current.map((record) => (
    record.id === recordId ? { ...record, reviewedAt: null } : record
  ))
  return writeWrongQuestionRecords(next)
}

export async function setWrongQuestionMistakeReason(
  recordId: string,
  mistakeReason: WrongQuestionMistakeReason,
): Promise<WrongQuestionRecord[]> {
  const current = await loadWrongQuestionRecords()
  const next = current.map((record) => (
    record.id === recordId
      ? {
          ...record,
          review: {
            ...record.review,
            mistakeReason,
            updatedAt: new Date().toISOString(),
          },
        }
      : record
  ))
  return writeWrongQuestionRecords(next)
}

export function extractWrongQuestionReviewContext(question: string): WrongQuestionReviewContext {
  const correctAnswer = question.match(/(?:正确答案|正確答案)\s*[:：]\s*([A-E])/i)?.[1]?.toUpperCase()
  const userAnswer = question.match(/我的答案\s*[:：]\s*([A-E])/i)?.[1]?.toUpperCase()

  return {
    ...(correctAnswer ? { correctAnswer } : {}),
    ...(userAnswer ? { userAnswer } : {}),
  }
}

function isWrongQuestionRecord(value: unknown): value is WrongQuestionRecord {
  if (!value || typeof value !== 'object') return false
  const record = value as Partial<WrongQuestionRecord>
  return (
    typeof record.id === 'string' &&
    typeof record.question === 'string' &&
    typeof record.createdAt === 'string' &&
    Boolean(record.candidate) &&
    typeof record.candidate?.id === 'string' &&
    (record.reviewedAt == null || typeof record.reviewedAt === 'string') &&
    isWrongQuestionReviewContext(record.review)
  )
}

function isWrongQuestionReviewContext(value: unknown): value is WrongQuestionReviewContext | undefined {
  if (value == null) return true
  if (typeof value !== 'object') return false
  const review = value as Partial<WrongQuestionReviewContext>
  return (
    (review.correctAnswer == null || /^[A-E]$/.test(review.correctAnswer)) &&
    (review.userAnswer == null || /^[A-E]$/.test(review.userAnswer)) &&
    (review.mistakeReason == null || isWrongQuestionMistakeReason(review.mistakeReason)) &&
    (review.updatedAt == null || typeof review.updatedAt === 'string')
  )
}

function isWrongQuestionMistakeReason(value: unknown): value is WrongQuestionMistakeReason {
  return (
    value === 'concept_confusion' ||
    value === 'missed_clue' ||
    value === 'differential_error' ||
    value === 'memory_gap'
  )
}

import React, { useState, useMemo } from 'react'
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  ScrollView,
} from 'react-native'
import { useLocalSearchParams, useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { appAlert } from '@/lib/app-dialog'
import { useExamSession } from '@/hooks/useExam'
import { useAuth } from '@/hooks/useAuth'
import { calculateScore } from '@/services/exam'
import { Colors, Typography, Spacing, BorderRadius, Shadows, getGrade } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { pageStyles } from '@/constants/pageStyles'
import { FeedbackLoopCard } from '@/components/FeedbackLoopCard'
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer'
import { uniqueWeakNodeIds } from '@/utils/learningFeedback'
import { supabase } from '@/lib/supabase'
import { resolveTarget } from '@/utils/routeBuilders'

export const options = { headerTitle: '考试' }

/** 多选题位掩码工具 */
function toggleBit(mask: number, bit: number): number {
  return mask & (1 << bit) ? mask ^ (1 << bit) : mask | (1 << bit)
}

function isBitSet(mask: number, bit: number): boolean {
  return (mask & (1 << bit)) !== 0
}

/** 选项字母标签 */
const OPTION_LABELS = ['A', 'B', 'C', 'D']

export default function ExamScreen() {
  const router = useRouter()
  const { user } = useAuth()
  const params = useLocalSearchParams<{ nodeIds: string; nodeTitle: string }>()

  const nodeIds = useMemo(() => {
    if (!params.nodeIds) return []
    try {
      return JSON.parse(params.nodeIds) as string[]
    } catch {
      return []
    }
  }, [params.nodeIds])

  const nodeTitle = params.nodeTitle || '综合测试'

  const [questionCount, setQuestionCount] = useState(10)
  const [difficulty, setDifficulty] = useState(2)
  const [examResult, setExamResult] = useState<{
    totalScore: number
    wrongQuestions: number[]
    sessionId: string
  } | null>(null)

  const openReviewTarget = async (nodeId: string) => {
    const { data, error } = await supabase
      .from('knowledge_nodes')
      .select('disease_id, chapter_section_id, content_class')
      .eq('id', nodeId)
      .maybeSingle()
    if (error) {
      appAlert('无法打开', '知识目标读取失败，请稍后重试。')
      return
    }
    const target = data ? resolveTarget(data) : null
    if (target) router.push(target)
  }

  const {
    questions,
    currentIndex,
    answers,
    loading,
    completed,
    currentQuestion,
    totalQuestions,
    answeredCount,
    startExam,
    answerQuestion,
    nextQuestion,
    prevQuestion,
    goToQuestion,
    finishExam,
  } = useExamSession(user?.id)

  const handleStart = async () => {
    if (nodeIds.length === 0) {
      appAlert('提示', '请先选择知识点范围')
      return
    }
    try {
      await startExam(nodeIds, questionCount, difficulty)
    } catch (e: any) {
      appAlert('生成失败', e.message || '请检查网络连接后重试')
    }
  }

  const handleFinish = async () => {
    const unanswered = totalQuestions - answeredCount
    if (unanswered > 0) {
      appAlert(
        '提示',
        `还有 ${unanswered} 题未作答，确定提交吗？`,
        [
          { text: '继续答题', style: 'cancel' },
          { text: '确定提交', style: 'destructive', onPress: doFinish },
        ]
      )
    } else {
      doFinish()
    }
  }

  const doFinish = async () => {
    try {
      const result = await finishExam()
      if (result) {
        setExamResult(result)
      }
    } catch (e: any) {
      appAlert('提交失败', e.message || '请重试')
    }
  }

  // ===================== 未开始状态 =====================
  if (questions.length === 0 && !loading) {
    return (
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.setupContent} showsVerticalScrollIndicator={false}>
          <View style={pageStyles.pageIntro}>
            <Text style={pageStyles.pageIntroTitleReading}>{nodeTitle}</Text>
            <Text style={pageStyles.pageIntroText}>
              {nodeIds.length > 0
                ? `围绕 ${nodeIds.length} 个知识点生成一轮短测。先作答，再根据错题决定下一步。`
                : '请从知识点页面选择范围后进入考试。'}
            </Text>
          </View>

          <View style={styles.configPanel}>
            <View style={styles.configSection}>
              <View style={styles.configHeading}>
                <View>
                  <Text style={styles.configLabel}>题目数量</Text>
                  <Text style={styles.configHint}>短测优先，完成后可围绕盲点再来一轮</Text>
                </View>
              </View>
            <View style={styles.chipRow}>
              {[5, 10, 15, 20].map(n => (
                <TouchableOpacity
                  key={n}
                  style={[styles.chip, questionCount === n && styles.chipActive]}
                  onPress={() => setQuestionCount(n)}
                >
                  <Text style={[styles.chipText, questionCount === n && styles.chipTextActive]}>
                    {n} 题
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            </View>

            <View style={[styles.configSection, styles.configSectionLast]}>
              <View style={styles.configHeading}>
                <View>
                  <Text style={styles.configLabel}>难度级别</Text>
                  <Text style={styles.configHint}>中等适合第一次检查理解</Text>
                </View>
              </View>
            <View style={styles.chipRow}>
              {[
                { value: 1, label: '简单' },
                { value: 2, label: '中等' },
                { value: 3, label: '困难' },
              ].map(d => (
                <TouchableOpacity
                  key={d.value}
                  style={[styles.chip, difficulty === d.value && styles.chipActive]}
                  onPress={() => setDifficulty(d.value)}
                >
                  <Text style={[styles.chipText, difficulty === d.value && styles.chipTextActive]}>
                    {d.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            </View>
          </View>

          <TouchableOpacity
            style={[styles.startBtn, nodeIds.length === 0 && styles.startBtnDisabled]}
            onPress={handleStart}
            disabled={nodeIds.length === 0}
          >
            <Text style={styles.startBtnText}>开始这一轮</Text>
            <Ionicons name="arrow-forward" size={18} color="#FFFDF9" />
          </TouchableOpacity>
          <Text style={styles.setupFootnote}>提交后会保留错题、解释与下一轮练习建议</Text>
        </ScrollView>
      </View>
    )
  }

  // ===================== 加载状态 =====================
  if (loading) {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary[500]} />
          <Text style={styles.loadingText}>正在生成题目...</Text>
          <Text style={styles.loadingSubtext}>AI 正在根据知识点内容出题，请稍候</Text>
        </View>
      </View>
    )
  }

  // ===================== 完成状态 =====================
  if (completed && examResult) {
    const scoreResult = calculateScore(questions, answers)
    const grade = getGrade(examResult.totalScore)
    const weakNodeIds = uniqueWeakNodeIds(scoreResult.wrongQuestions, questions)
    const retryCount = Math.max(3, Math.min(10, scoreResult.wrongQuestions.length * 2))

    return (
      <View style={styles.container}>
        <ScrollView contentContainerStyle={styles.resultContent}>
          {/* 分数展示 */}
          <View style={styles.scoreCard}>
            <Text style={styles.scoreLabel}>这一轮的理解完成度</Text>
            <Text style={[styles.scoreValue, { color: grade.color }]}>
              {examResult.totalScore}
            </Text>
            <Text style={[styles.scoreGrade, { color: grade.color }]}>{grade.label}</Text>
            <Text style={styles.scoreDetail}>
              答对 {scoreResult.correctCount} / {totalQuestions} 题
            </Text>
          </View>

          {scoreResult.wrongQuestions.length > 0 ? (
            <FeedbackLoopCard
              title={`先修正这 ${scoreResult.wrongQuestions.length} 个暴露点`}
              summary="错题不是失败记录，而是下一轮练习的导航。"
              action={`围绕关联知识点再做 ${retryCount} 道短测，立即验证是否真正修正。`}
            />
          ) : (
            <FeedbackLoopCard
              title="这一轮没有明显盲点"
              summary="完成得很好，但一次正确不等于永久掌握。"
              action="换一组题或提高难度，用新的作品继续获取反馈。"
            />
          )}

          {/* 错题解析 */}
          {scoreResult.wrongQuestions.length > 0 && (
            <View style={styles.wrongSection}>
              <Text style={styles.wrongTitle}>
                错题解析（{scoreResult.wrongQuestions.length} 题）
              </Text>
              {scoreResult.wrongQuestions.map(qIdx => {
                const q = questions[qIdx]
                if (!q) return null
                return (
                  <View key={q.id} style={styles.wrongCard}>
                    <View style={styles.wrongHeader}>
                      <Text style={styles.wrongIndex}>第 {qIdx + 1} 题</Text>
                      <Text style={styles.wrongType}>
                        {q.type === 'single' ? '单选' : '多选'}
                      </Text>
                    </View>
                    <Text style={styles.wrongQuestion}>{q.question}</Text>

                    {/* 显示正确答案 */}
                    <View style={styles.answerRow}>
                      <Text style={styles.correctLabel}>正确答案：</Text>
                      <Text style={styles.correctAnswer}>
                        {q.type === 'single'
                          ? OPTION_LABELS[q.answer]
                          : q.options
                              .map((_, i) => isBitSet(q.answer, i) ? OPTION_LABELS[i] : null)
                              .filter(Boolean)
                              .join('、')}
                      </Text>
                    </View>

                    {/* 显示用户答案 */}
                    <View style={styles.answerRow}>
                      <Text style={styles.userLabel}>你的答案：</Text>
                      <Text style={[
                        styles.userAnswer,
                        answers[qIdx] === undefined && styles.unansweredText,
                      ]}>
                        {answers[qIdx] === undefined
                          ? '未作答'
                          : q.type === 'single'
                            ? OPTION_LABELS[answers[qIdx]]
                            : q.options
                                .map((_, i) => isBitSet(answers[qIdx], i) ? OPTION_LABELS[i] : null)
                                .filter(Boolean)
                                .join('、') || '未作答'}
                      </Text>
                    </View>

                    <Text style={styles.explanation}>{q.explanation}</Text>
                  </View>
                )
              })}
            </View>
          )}

          {/* 薄弱知识点 */}
          {examResult.wrongQuestions.length > 0 && (
            <View style={styles.weakSection}>
              <Text style={styles.weakTitle}>建议复习</Text>
              {Array.from(
                new Set(
                  examResult.wrongQuestions
                    .map(i => questions[i]?.related_nodes || [])
                    .flat()
                )
              ).map((nodeId, idx) => (
                <TouchableOpacity
                  key={nodeId}
                  style={styles.weakItem}
                  onPress={() => void openReviewTarget(nodeId)}
                >
                  <View style={styles.weakItemIcon}>
                    <Ionicons name="book-outline" size={17} color={Colors.primary[700]} />
                  </View>
                  <Text style={styles.weakItemText}>知识点 {idx + 1}</Text>
                  <Ionicons name="arrow-forward" size={16} color={Colors.primary[700]} />
                </TouchableOpacity>
              ))}
            </View>
          )}

          <MedicalDisclaimer />

          {/* 操作按钮 */}
          <View style={styles.resultActions}>
            <TouchableOpacity
              style={styles.retryBtn}
              onPress={async () => {
                setExamResult(null)
                await startExam(
                  weakNodeIds.length > 0 ? weakNodeIds : nodeIds,
                  scoreResult.wrongQuestions.length > 0 ? retryCount : questionCount,
                  scoreResult.wrongQuestions.length > 0 ? difficulty : Math.min(3, difficulty + 1)
                )
              }}
            >
              <Text style={styles.retryBtnText}>
                {scoreResult.wrongQuestions.length > 0 ? '围绕盲点再测一轮' : '提高难度再测'}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.backHomeBtn}
              onPress={() => router.back()}
            >
              <Text style={styles.backHomeBtnText}>返回</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </View>
    )
  }

  // ===================== 答题状态 =====================
  if (!currentQuestion) return null

  const progress = totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0
  const isCurrentAnswered = answers[currentIndex] !== undefined

  return (
    <View style={styles.container}>
      {/* 进度条 */}
      <View style={styles.progressContainer}>
        <View style={styles.progressBar}>
          <View style={[styles.progressFill, { width: `${progress}%` }]} />
        </View>
        <Text style={styles.progressText}>
          {answeredCount} / {totalQuestions}
        </Text>
      </View>

      {/* 题号导航 */}
      <ScrollView horizontal style={styles.questionNav} showsHorizontalScrollIndicator={false}>
        {questions.map((_, i) => (
          <TouchableOpacity
            key={i}
            style={[
              styles.questionDot,
              i === currentIndex && styles.questionDotCurrent,
              answers[i] !== undefined && styles.questionDotAnswered,
            ]}
            onPress={() => goToQuestion(i)}
          >
            <Text
              style={[
                styles.questionDotText,
                i === currentIndex && styles.questionDotTextCurrent,
                answers[i] !== undefined && i !== currentIndex && styles.questionDotTextAnswered,
              ]}
            >
              {i + 1}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView contentContainerStyle={styles.examContent}>
        {/* 题目 */}
        <View style={styles.questionCard}>
          <View style={styles.questionHeader}>
            <Text style={styles.questionIndex}>
              第 {currentIndex + 1} 题
            </Text>
            <View style={[
              styles.typeBadge,
              currentQuestion.type === 'multiple' && styles.typeBadgeMultiple,
            ]}>
              <Text style={styles.typeBadgeText}>
                {currentQuestion.type === 'single' ? '单选' : '多选'}
              </Text>
            </View>
          </View>
          <Text style={styles.questionText}>{currentQuestion.question}</Text>
        </View>

        {/* 选项 */}
        <View style={styles.optionsContainer}>
          {currentQuestion.options.map((option, optIdx) => {
            const isSelected = currentQuestion.type === 'single'
              ? answers[currentIndex] === optIdx
              : answers[currentIndex] !== undefined && isBitSet(answers[currentIndex], optIdx)

            return (
              <TouchableOpacity
                key={optIdx}
                style={[styles.optionItem, isSelected && styles.optionItemSelected]}
                onPress={() => {
                  if (currentQuestion.type === 'single') {
                    answerQuestion(currentIndex, optIdx)
                  } else {
                    const currentMask = answers[currentIndex] ?? 0
                    answerQuestion(currentIndex, toggleBit(currentMask, optIdx))
                  }
                }}
              >
                <View style={[styles.optionCircle, isSelected && styles.optionCircleSelected]}>
                  <Text style={[styles.optionLabel, isSelected && styles.optionLabelSelected]}>
                    {OPTION_LABELS[optIdx]}
                  </Text>
                </View>
                <Text style={[styles.optionText, isSelected && styles.optionTextSelected]}>
                  {option}
                </Text>
              </TouchableOpacity>
            )
          })}
        </View>
      </ScrollView>

      {/* 底部操作栏 */}
      <View style={styles.bottomBar}>
        <TouchableOpacity
          style={[styles.navBtn, currentIndex === 0 && styles.navBtnDisabled]}
          onPress={prevQuestion}
          disabled={currentIndex === 0}
        >
          <Text style={[styles.navBtnText, currentIndex === 0 && styles.navBtnTextDisabled]}>
            上一题
          </Text>
        </TouchableOpacity>

        {currentIndex < totalQuestions - 1 ? (
          <TouchableOpacity style={styles.navBtn} onPress={nextQuestion}>
            <Text style={styles.navBtnText}>下一题</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={[styles.submitExamBtn, !isCurrentAnswered && styles.submitExamBtnDisabled]}
            onPress={handleFinish}
          >
            <Text style={styles.submitExamBtnText}>交卷</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },

  // ---- 通用 ----
  backLink: {
    color: Colors.primary[500],
    ...Typography.bodySmall,
    padding: Spacing.base,
  },

  // ---- 未开始状态 ----
  setupContent: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Spacing['4xl'],
  },
  configPanel: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
    marginBottom: Spacing.lg,
  },
  configSection: {
    paddingVertical: Spacing.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  configSectionLast: {
    borderBottomWidth: 0,
  },
  configHeading: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },

  configLabel: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  configHint: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  chip: {
    flex: 1,
    minWidth: 64,
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.neutral[50],
    borderWidth: 1,
    borderColor: Colors.border,
  },
  chipActive: {
    backgroundColor: Colors.ink,
    borderColor: Colors.ink,
  },
  chipText: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
  },
  chipTextActive: {
    color: '#FFFDF9',
    fontWeight: '600',
  },
  startBtn: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: Spacing.sm,
    minHeight: 52,
    backgroundColor: Colors.ink,
    paddingHorizontal: Spacing['2xl'],
    borderRadius: BorderRadius.full,
    alignItems: 'center',
  },
  startBtnDisabled: {
    opacity: 0.5,
  },
  startBtnText: {
    ...Typography.labelLarge,
    color: '#FFFDF9',
    fontWeight: '600',
  },
  setupFootnote: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    textAlign: 'center',
    marginTop: Spacing.sm,
  },

  // ---- 加载状态 ----
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
    marginTop: Spacing.base,
  },
  loadingSubtext: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },

  // ---- 答题状态 ----
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.base,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xs,
  },
  progressBar: {
    flex: 1,
    height: 6,
    backgroundColor: Colors.surfaceVariant,
    borderRadius: BorderRadius.full,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: Colors.primary[500],
    borderRadius: BorderRadius.full,
  },
  progressText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginLeft: Spacing.sm,
    minWidth: 50,
    textAlign: 'right',
  },
  questionNav: {
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm,
    maxHeight: 48,
  },
  questionDot: {
    width: 32,
    height: 32,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceVariant,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.xs,
  },
  questionDotCurrent: {
    backgroundColor: Colors.primary[500],
  },
  questionDotAnswered: {
    backgroundColor: Colors.primary[100],
  },
  questionDotText: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  questionDotTextCurrent: {
    color: '#fff',
    fontWeight: '600',
  },
  questionDotTextAnswered: {
    color: Colors.primary[600],
  },
  examContent: {
    padding: Spacing.base,
    paddingBottom: 100,
  },
  questionCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.base,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
    marginBottom: Spacing.base,
  },
  questionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  questionIndex: {
    ...Typography.labelMedium,
    color: Colors.primary[600],
    marginRight: Spacing.sm,
  },
  typeBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
    backgroundColor: Colors.primaryLight,
  },
  typeBadgeMultiple: {
    backgroundColor: '#FEF3C7',
  },
  typeBadgeText: {
    ...Typography.labelSmall,
    color: Colors.primary[600],
  },
  questionText: {
    ...Typography.bodyLarge,
    color: Colors.textPrimary,
    lineHeight: 24,
  },
  optionsContainer: {
    gap: Spacing.sm,
  },
  optionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    borderWidth: 1.5,
    borderColor: Colors.border,
  },
  optionItemSelected: {
    borderColor: Colors.primary[500],
    backgroundColor: Colors.primaryLight,
  },
  optionCircle: {
    width: 28,
    height: 28,
    borderRadius: BorderRadius.full,
    borderWidth: 2,
    borderColor: Colors.neutral[300],
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.md,
  },
  optionCircleSelected: {
    borderColor: Colors.primary[500],
    backgroundColor: Colors.primary[500],
  },
  optionLabel: {
    ...Typography.labelSmall,
    color: Colors.textSecondary,
  },
  optionLabelSelected: {
    color: '#fff',
    fontWeight: '600',
  },
  optionText: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
  },
  optionTextSelected: {
    color: Colors.primary[700],
    fontWeight: '500',
  },

  // ---- 底部操作栏 ----
  bottomBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: Spacing.base,
    backgroundColor: Colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  navBtn: {
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.xl,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceVariant,
  },
  navBtnDisabled: {
    opacity: 0.4,
  },
  navBtnText: {
    ...Typography.labelLarge,
    color: Colors.textPrimary,
  },
  navBtnTextDisabled: {
    color: Colors.textTertiary,
  },
  submitExamBtn: {
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.xl,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[500],
  },
  submitExamBtnDisabled: {
    opacity: 0.6,
  },
  submitExamBtnText: {
    ...Typography.labelLarge,
    color: '#fff',
  },

  // ---- 完成状态 ----
  resultContent: {
    padding: Spacing.base,
    paddingBottom: Spacing['3xl'],
  },
  scoreCard: {
    backgroundColor: Colors.ink,
    borderRadius: BorderRadius.xl,
    padding: Spacing.xl,
    alignItems: 'center',
    ...Shadows.level2,
    marginBottom: Spacing.xl,
  },
  scoreLabel: {
    ...Typography.labelMedium,
    color: 'rgba(255, 253, 249, 0.62)',
    marginBottom: Spacing.xs,
  },
  scoreValue: {
    ...Typography.numberXL,
    fontSize: 64,
    lineHeight: 68,
  },
  scoreGrade: {
    ...Typography.titleMedium,
    marginTop: Spacing.xs,
  },
  scoreDetail: {
    ...Typography.bodySmall,
    color: 'rgba(255, 253, 249, 0.62)',
    marginTop: Spacing.sm,
  },
  wrongSection: {
    marginBottom: Spacing.xl,
  },
  wrongTitle: {
    ...Typography.titleMedium,
    color: Colors.error,
    marginBottom: Spacing.md,
  },
  wrongCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.base,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
    marginBottom: Spacing.md,
  },
  wrongHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  wrongIndex: {
    ...Typography.labelMedium,
    color: Colors.error,
    marginRight: Spacing.sm,
  },
  wrongType: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  wrongQuestion: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    lineHeight: 21,
    marginBottom: Spacing.sm,
  },
  answerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.xs,
  },
  correctLabel: {
    ...Typography.labelSmall,
    color: Colors.success,
  },
  correctAnswer: {
    ...Typography.labelSmall,
    color: Colors.success,
    fontWeight: '600',
  },
  userLabel: {
    ...Typography.labelSmall,
    color: Colors.textSecondary,
  },
  userAnswer: {
    ...Typography.labelSmall,
    color: Colors.error,
    fontWeight: '600',
  },
  unansweredText: {
    color: Colors.textTertiary,
  },
  explanation: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    lineHeight: 18,
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  weakSection: {
    marginBottom: Spacing.xl,
  },
  weakTitle: {
    ...Typography.titleMedium,
    color: Colors.warning,
    marginBottom: Spacing.md,
  },
  weakItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  weakItemIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
    marginRight: Spacing.sm,
  },
  weakItemText: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
  },
  resultActions: {
    gap: Spacing.sm,
  },
  retryBtn: {
    backgroundColor: Colors.primary[500],
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    alignItems: 'center',
  },
  retryBtnText: {
    ...Typography.labelLarge,
    color: '#fff',
  },
  backHomeBtn: {
    backgroundColor: Colors.surfaceVariant,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    alignItems: 'center',
  },
  backHomeBtnText: {
    ...Typography.labelLarge,
    color: Colors.textPrimary,
  },
})

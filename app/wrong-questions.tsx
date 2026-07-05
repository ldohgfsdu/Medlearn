import { useCallback, useState } from 'react'
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, type Href, useFocusEffect, useRouter } from 'expo-router'
import { BorderRadius, Colors, FontFamily, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import {
  loadWrongQuestionRecords,
  markWrongQuestionReviewed,
  reactivateWrongQuestionRecord,
  setWrongQuestionMistakeReason,
  type WrongQuestionMistakeReason,
  type WrongQuestionRecord,
} from '@/services/wrongQuestionService'

type QueueMode = 'active' | 'reviewed'

const MISTAKE_REASONS: readonly { id: WrongQuestionMistakeReason; label: string }[] = [
  { id: 'missed_clue', label: '漏看线索' },
  { id: 'differential_error', label: '鉴别错误' },
  { id: 'concept_confusion', label: '概念混淆' },
  { id: 'memory_gap', label: '记忆不牢' },
]

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function WeaknessRecordRow({
  onOpen,
  onSetMistakeReason,
  onToggleReviewed,
  record,
  testID,
}: {
  onOpen: () => void
  onSetMistakeReason: (reason: WrongQuestionMistakeReason) => void
  onToggleReviewed: () => void
  record: WrongQuestionRecord
  testID?: string
}) {
  const reviewed = Boolean(record.reviewedAt)
  const candidate = record.candidate
  const review = record.review
  const hasAnswerContext = Boolean(review?.userAnswer || review?.correctAnswer)

  return (
    <View style={styles.recordRow} testID={testID}>
      <View style={styles.recordHeader}>
        <View style={styles.recordIcon}>
          <Ionicons name={reviewed ? 'checkmark-circle' : 'alert-circle-outline'} size={18} color={reviewed ? Colors.success : Colors.warning} />
        </View>
        <View style={styles.recordTitleCopy}>
          <Text style={styles.recordTitle} numberOfLines={2}>{candidate.itemTitle || candidate.groupTitle}</Text>
          <Text style={styles.recordMeta} numberOfLines={1}>
            {candidate.unitTitle} · {candidate.pageLabel} · {formatDate(record.createdAt)}
          </Text>
        </View>
      </View>

      <Text style={styles.questionText} numberOfLines={3}>{record.question}</Text>
      {hasAnswerContext ? (
        <View style={styles.answerRow}>
          {review?.userAnswer ? (
            <View style={styles.answerPill}>
              <Text style={styles.answerLabel}>我的答案</Text>
              <Text style={styles.answerValue}>{review.userAnswer}</Text>
            </View>
          ) : null}
          {review?.correctAnswer ? (
            <View style={styles.answerPill}>
              <Text style={styles.answerLabel}>正确答案</Text>
              <Text style={styles.answerValue}>{review.correctAnswer}</Text>
            </View>
          ) : null}
        </View>
      ) : null}
      <Text style={styles.evidenceText} numberOfLines={3}>{candidate.evidenceExcerpt}</Text>

      <View style={styles.reasonBlock}>
        <Text style={styles.reasonTitle}>这次主要卡在哪里</Text>
        <View style={styles.reasonChipRow}>
          {MISTAKE_REASONS.map((reason) => {
            const selected = review?.mistakeReason === reason.id
            return (
              <Pressable
                key={reason.id}
                style={[styles.reasonChip, selected && styles.reasonChipActive]}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                onPress={() => onSetMistakeReason(reason.id)}
                testID={testID ? `${testID}-reason-${reason.id}` : undefined}
              >
                <Text style={[styles.reasonChipText, selected && styles.reasonChipTextActive]}>{reason.label}</Text>
              </Pressable>
            )
          })}
        </View>
      </View>

      <View style={styles.actionRow}>
        <TouchableOpacity
          style={styles.secondaryButton}
          activeOpacity={0.72}
          onPress={onToggleReviewed}
          testID={testID ? `${testID}-toggle-reviewed` : undefined}
        >
          <Ionicons name={reviewed ? 'refresh-outline' : 'checkmark-outline'} size={16} color={Colors.primary[700]} />
          <Text style={styles.secondaryButtonText}>{reviewed ? '重新加入' : '标记已复习'}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.primaryButton}
          activeOpacity={0.78}
          onPress={onOpen}
          testID={testID ? `${testID}-open-textbook` : undefined}
        >
          <Text style={styles.primaryButtonText}>打开教材</Text>
          <Ionicons name="arrow-forward" size={15} color={Colors.surface} />
        </TouchableOpacity>
      </View>
    </View>
  )
}

export default function WrongQuestionsScreen() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [records, setRecords] = useState<WrongQuestionRecord[]>([])
  const [mode, setMode] = useState<QueueMode>('active')

  const refresh = useCallback(() => {
    let mounted = true
    setLoading(true)
    loadWrongQuestionRecords()
      .then((next) => {
        if (mounted) setRecords(next)
      })
      .catch(() => {
        if (mounted) setRecords([])
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [])

  useFocusEffect(refresh)

  const activeRecords = records.filter((record) => !record.reviewedAt)
  const reviewedRecords = records.filter((record) => record.reviewedAt)
  const visibleRecords = mode === 'active' ? activeRecords : reviewedRecords

  const openRecord = (record: WrongQuestionRecord) => {
    router.push({
      pathname: '/textbook/[sectionId]/unit/[unitId]',
      params: {
        sectionId: record.candidate.sectionId,
        unitId: record.candidate.unitId,
        targetItemId: record.candidate.itemId || record.candidate.id.split(':').pop(),
        from: 'wrong-question',
      },
    } as unknown as Href)
  }

  const toggleReviewed = async (record: WrongQuestionRecord) => {
    const next = record.reviewedAt
      ? await reactivateWrongQuestionRecord(record.id)
      : await markWrongQuestionReviewed(record.id)
    setRecords(next)
  }

  const setMistakeReason = async (
    record: WrongQuestionRecord,
    reason: WrongQuestionMistakeReason,
  ) => {
    const next = await setWrongQuestionMistakeReason(record.id, reason)
    setRecords(next)
  }

  return (
    <View style={styles.screen}>
      <Stack.Screen options={{ headerTitle: '错题弱点' }} />
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.intro}>
          <Text style={styles.introTitle}>把错题留成一个可复习的位置</Text>
          <Text style={styles.introText}>
            这里保存题干、教材位置、证据摘录和页码。复习时先回到教材原文，再决定是否标记已复习。
          </Text>
        </View>

        <View style={styles.summaryBand}>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryValue}>{activeRecords.length}</Text>
            <Text style={styles.summaryLabel}>待复习</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryItem}>
            <Text style={styles.summaryValue}>{reviewedRecords.length}</Text>
            <Text style={styles.summaryLabel}>已复习</Text>
          </View>
        </View>

        <View style={styles.segmented}>
          <Pressable
            style={[styles.segment, mode === 'active' && styles.segmentActive]}
            accessibilityRole="button"
            testID="wrong-question-active-segment"
            onPress={() => setMode('active')}
          >
            <Text style={[styles.segmentText, mode === 'active' && styles.segmentTextActive]}>待复习</Text>
          </Pressable>
          <Pressable
            style={[styles.segment, mode === 'reviewed' && styles.segmentActive]}
            accessibilityRole="button"
            testID="wrong-question-reviewed-segment"
            onPress={() => setMode('reviewed')}
          >
            <Text style={[styles.segmentText, mode === 'reviewed' && styles.segmentTextActive]}>已复习</Text>
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.stateBlock}>
            <ActivityIndicator color={Colors.primary[700]} />
            <Text style={styles.stateText}>正在读取弱点记录</Text>
          </View>
        ) : null}

        {!loading && visibleRecords.length === 0 ? (
          <View style={styles.stateBlock}>
            <Ionicons name="document-text-outline" size={30} color={Colors.neutral[300]} />
            <Text style={styles.stateTitle}>{mode === 'active' ? '还没有待复习弱点' : '还没有已复习记录'}</Text>
            <Text style={styles.stateText}>
              {mode === 'active'
                ? '从知识地图粘贴错题，保存一个教材证据位置后会出现在这里。'
                : '待复习条目标记完成后，会移到这里。'}
            </Text>
            {mode === 'active' ? (
              <TouchableOpacity style={styles.emptyAction} activeOpacity={0.78} onPress={() => router.push('/map')}>
                <Text style={styles.emptyActionText}>去定位错题</Text>
                <Ionicons name="arrow-forward" size={15} color={Colors.surface} />
              </TouchableOpacity>
            ) : null}
          </View>
        ) : null}

        {!loading && visibleRecords.length > 0 ? (
          <View style={styles.recordList}>
            {visibleRecords.map((record) => (
              <WeaknessRecordRow
                key={record.id}
                record={record}
                onOpen={() => openRecord(record)}
                onSetMistakeReason={(reason) => setMistakeReason(record, reason)}
                onToggleReviewed={() => toggleReviewed(record)}
                testID="wrong-question-record"
              />
            ))}
          </View>
        ) : null}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Layout.screenPaddingBottom,
  },
  intro: {
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.md,
  },
  introTitle: {
    fontSize: 26,
    lineHeight: 32,
    color: Colors.textPrimary,
    fontWeight: '600',
    fontFamily: FontFamily.sans,
  },
  introText: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  summaryBand: {
    minHeight: 76,
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    marginBottom: Spacing.md,
  },
  summaryItem: {
    flex: 1,
    alignItems: 'center',
  },
  summaryValue: {
    ...Typography.numberXL,
    fontFamily: FontFamily.sans,
    fontVariant: ['tabular-nums'],
    color: Colors.textPrimary,
  },
  summaryLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  summaryDivider: {
    width: StyleSheet.hairlineWidth,
    height: 40,
    backgroundColor: Colors.border,
  },
  segmented: {
    minHeight: 44,
    flexDirection: 'row',
    padding: 3,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceVariant,
    marginBottom: Spacing.md,
  },
  segment: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: BorderRadius.full,
  },
  segmentActive: {
    backgroundColor: Colors.surface,
  },
  segmentText: {
    ...Typography.labelLarge,
    color: Colors.textTertiary,
    fontWeight: '600',
  },
  segmentTextActive: {
    color: Colors.primary[700],
  },
  recordList: {
    gap: Spacing.md,
  },
  recordRow: {
    gap: Spacing.sm,
    padding: Layout.cardPadding,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  recordHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  recordIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
  },
  recordTitleCopy: {
    flex: 1,
  },
  recordTitle: {
    ...Typography.titleSmall,
    fontFamily: FontFamily.serif,
    color: Colors.textPrimary,
  },
  recordMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  questionText: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
  },
  answerRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  answerPill: {
    minHeight: 32,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[50],
  },
  answerLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  answerValue: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
    fontWeight: '600',
  },
  evidenceText: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
  },
  reasonBlock: {
    gap: Spacing.xs,
    paddingTop: Spacing.xs,
  },
  reasonTitle: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  reasonChipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  reasonChip: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  reasonChipActive: {
    borderColor: Colors.primary[700],
    backgroundColor: Colors.primary[50],
  },
  reasonChipText: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
    fontWeight: '600',
  },
  reasonChipTextActive: {
    color: Colors.primary[700],
  },
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
    paddingTop: Spacing.xs,
  },
  secondaryButton: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.sm,
  },
  secondaryButtonText: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
    fontWeight: '600',
  },
  primaryButton: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[700],
  },
  primaryButtonText: {
    ...Typography.labelMedium,
    color: Colors.surface,
    fontWeight: '600',
  },
  stateBlock: {
    minHeight: 190,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  stateTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
    marginTop: Spacing.sm,
  },
  stateText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    textAlign: 'center',
    marginTop: Spacing.xs,
  },
  emptyAction: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.lg,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[700],
    marginTop: Spacing.md,
  },
  emptyActionText: {
    ...Typography.labelLarge,
    color: Colors.surface,
    fontWeight: '600',
  },
})

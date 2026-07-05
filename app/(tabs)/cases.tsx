import { useEffect, useState } from 'react'
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator, Modal } from 'react-native'
import { appAlert } from '@/lib/app-dialog'
import { useLocalSearchParams, useNavigation, useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { resolveCaseTemplate, type CaseTemplateSummary } from '@/hooks/useCaseSession'
import { supabase } from '@/lib/supabase'
import { caseEngine } from '@/services/case-engine'
import {
  getDifficultyLabel,
  recommendStretchDifficulty,
  type CaseDifficulty,
} from '@/utils/learningChallenge'
import { Colors, Typography, Spacing, BorderRadius, FontFamily, getMasteryColor } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { FLOATING_TAB_BAR_BASE_HEIGHT } from './_layout'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { CHIEF_COMPLAINTS } from '@/constants/vindicate'
import { getTotalScore, parseScoreReport } from '@/utils/scoreReport'

type CaseMode = 'clinical' | 'exam'

const COMPLAINT_META: Record<string, {
  icon: keyof typeof Ionicons.glyphMap
  cue: string
}> = {
  chest_pain: { icon: 'heart-outline', cue: '心血管 · 呼吸 · 消化' },
  dyspnea: { icon: 'cloud-outline', cue: '气道 · 肺循环' },
  abdominal_pain: { icon: 'body-outline', cue: '定位 · 性质 · 伴随症状' },
  fever: { icon: 'thermometer-outline', cue: '感染 · 炎症 · 肿瘤' },
  ams: { icon: 'flash-outline', cue: '神经 · 代谢 · 中毒' },
}

const CHIEF_COMPLAINT_LABELS: Record<string, string> = Object.fromEntries(
  CHIEF_COMPLAINTS.map((complaint) => [complaint.id, complaint.label]),
)

function buildLearnerSafeCaseTitle(chiefComplaint?: string | null): string {
  const label = chiefComplaint ? CHIEF_COMPLAINT_LABELS[chiefComplaint] ?? chiefComplaint : ''
  return label ? `${label}病例复盘` : '病例复盘'
}

export default function CasesScreen() {
  const router = useRouter()
  const navigation = useNavigation()
  const insets = useSafeAreaInsets()
  const { section } = useLocalSearchParams<{ section?: string }>()
  const showHistoryFirst = section === 'history'
  const { user } = useAuth()

  useEffect(() => {
    navigation.setOptions({
      headerTitle: showHistoryFirst ? '病例记录' : '病例中心',
    })
  }, [navigation, showHistoryFirst])
  const [loading, setLoading] = useState<string | null>(null)
  const [pendingChiefComplaint, setPendingChiefComplaint] = useState<string | null>(null)
  const [caseMode, setCaseMode] = useState<CaseMode>('clinical')
  const { data: completedSessions = [] } = useQuery({
    queryKey: ['completedCaseSessions', user?.id],
    enabled: Boolean(user),
    queryFn: async () => {
      const { data, error } = await supabase
        .from('case_sessions')
        .select('id, case_id, score, completed_at, case_templates(title, chief_complaint)')
        .eq('user_id', user!.id)
        .eq('status', 'completed')
        .order('completed_at', { ascending: false })
        .limit(10)

      if (error) throw error
      return (data ?? []).map((session) => ({
        ...session,
        score: parseScoreReport(session.score),
      }))
    },
  })

  const getRecommendedDifficulty = (chiefComplaint: string): CaseDifficulty => {
    const latestSession = completedSessions.find((session) => {
      const template = resolveCaseTemplate(
        session.case_templates as CaseTemplateSummary | CaseTemplateSummary[] | null,
      )
      return template?.chief_complaint === chiefComplaint
    })
    return recommendStretchDifficulty(getTotalScore(latestSession?.score))
  }

  const handleStartCase = async (chiefComplaint: string) => {
    if (!user) {
      appAlert('提示', '请先登录')
      return
    }

    if (!user.user_metadata?.medlearn_disclaimer_ack_at) {
      setPendingChiefComplaint(chiefComplaint)
      return
    }

    await startCase(chiefComplaint, user.id, getRecommendedDifficulty(chiefComplaint))
  }

  const handleAcceptDisclaimer = async () => {
    if (!pendingChiefComplaint || !user) return
    try {
      await supabase.auth.updateUser({
        data: { medlearn_disclaimer_ack_at: new Date().toISOString() },
      })
    } catch (e: any) {
      console.warn('[disclaimer] save failed:', e?.message)
      appAlert('提示', '免责声明记录保存失败，下次进入时可能再次提示。')
    }
    const chiefComplaint = pendingChiefComplaint
    setPendingChiefComplaint(null)
    await startCase(chiefComplaint, user.id, getRecommendedDifficulty(chiefComplaint))
  }

  const startCase = async (
    chiefComplaint: string,
    userId: string,
    recommendedDifficulty: CaseDifficulty
  ) => {
    setLoading(chiefComplaint)
    try {
      const { data: cases } = await supabase
        .from('case_templates')
        .select('id, title, difficulty')
        .eq('chief_complaint', chiefComplaint)
        .eq('is_active', true)
        .eq('review_status', 'approved')
        .limit(5)

      if (!cases || cases.length === 0) {
        appAlert('提示', '该主诉下暂无可用病例')
        return
      }

      const selected = cases.find((item) => item.difficulty === recommendedDifficulty) || cases[0]
      const { sessionId } = await caseEngine.startCase(selected.id, userId)
      router.push(`/case/${sessionId}/chat`)
    } catch (e: any) {
      appAlert('错误', e.message || '启动病例失败')
    } finally {
      setLoading(null)
    }
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[
        styles.content,
        { paddingBottom: FLOATING_TAB_BAR_BASE_HEIGHT + insets.bottom + Spacing.lg },
      ]}
      showsVerticalScrollIndicator={false}
    >
      {!showHistoryFirst && (
        <>
          <View style={styles.pageIntro}>
            <Text style={styles.pageIntroTitle}>从一个主诉开始</Text>
            <Text style={styles.pageIntroText}>
              临床模式训练问诊、查体、检查、诊断与治疗；应试模式等待真实题源接入后开放。
            </Text>
          </View>

          <View style={styles.modeSwitch}>
            <TouchableOpacity
              style={[styles.modeButton, caseMode === 'clinical' && styles.modeButtonActive]}
              activeOpacity={0.72}
              onPress={() => setCaseMode('clinical')}
              testID="case-mode-clinical"
            >
              <Text style={[styles.modeButtonText, caseMode === 'clinical' && styles.modeButtonTextActive]}>
                临床模式
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.modeButton, caseMode === 'exam' && styles.modeButtonActive]}
              activeOpacity={0.72}
              onPress={() => setCaseMode('exam')}
              testID="case-mode-exam"
            >
              <Text style={[styles.modeButtonText, caseMode === 'exam' && styles.modeButtonTextActive]}>
                应试模式
              </Text>
            </TouchableOpacity>
          </View>

          {caseMode === 'clinical' ? (
            <>
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionTitle}>选择主诉</Text>
                <Text style={styles.sectionMeta}>随机病例</Text>
              </View>

              <View style={styles.cardGrid}>
                {CHIEF_COMPLAINTS.map((complaint) => {
                  const meta = COMPLAINT_META[complaint.id]
                  const recommendedDifficulty = getRecommendedDifficulty(complaint.id)
                  return (
                    <TouchableOpacity
                      key={complaint.id}
                      style={styles.caseCard}
                      onPress={() => handleStartCase(complaint.id)}
                      disabled={loading !== null}
                      activeOpacity={0.75}
                    >
                      <View style={styles.caseIconWrap}>
                        <Ionicons name={meta.icon} size={20} color={Colors.ink} />
                      </View>
                      <Text style={styles.caseTitle}>{complaint.label}</Text>
                      <Text style={styles.caseSubtitle} numberOfLines={1}>{meta.cue}</Text>
                      <Text style={styles.difficultyHint}>
                        建议 · {getDifficultyLabel(recommendedDifficulty)}
                      </Text>
                      {loading === complaint.id && (
                        <View style={styles.loadingOverlay}>
                          <ActivityIndicator size="small" color={Colors.primary[700]} />
                        </View>
                      )}
                    </TouchableOpacity>
                  )
                })}
              </View>
            </>
          ) : (
            <View style={styles.examModeCard} testID="case-exam-mode-placeholder">
              <View style={styles.examModeIcon}>
                <Ionicons name="school-outline" size={22} color={Colors.primary[700]} />
              </View>
              <View style={styles.examModeCopy}>
                <Text style={styles.examModeTitle}>应试模式待题源接入</Text>
                <Text style={styles.examModeText}>
                  这里会承接真实题干、选项、答案与解析。未接入前不生成模拟真题，避免把未经审核的题目当成练习材料。
                </Text>
                <TouchableOpacity
                  style={styles.examModeAction}
                  activeOpacity={0.74}
                  onPress={() => router.push('/wrong-questions' as const)}
                >
                  <Text style={styles.examModeActionText}>先查看错题弱点</Text>
                  <Ionicons name="arrow-forward" size={15} color={Colors.surface} />
                </TouchableOpacity>
              </View>
            </View>
          )}
        </>
      )}

      {showHistoryFirst && (
        <TouchableOpacity
          style={styles.historyBackLink}
          onPress={() => router.replace('/(tabs)/cases')}
          activeOpacity={0.7}
        >
          <Ionicons name="pulse-outline" size={16} color={Colors.primary[700]} />
          <Text style={styles.historyBackText}>去开始新病例</Text>
        </TouchableOpacity>
      )}

      <View style={[styles.sectionHeader, !showHistoryFirst && styles.historyHeader]}>
        <Text style={styles.sectionTitle}>病例记录</Text>
        <Text style={styles.sectionMeta}>{completedSessions.length} 次完成</Text>
      </View>

      {completedSessions.length === 0 ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyTitle}>暂无病例记录</Text>
          <Text style={styles.emptySubtitle}>完成一次病例训练后，这里会显示评分与复盘记录。</Text>
        </View>
      ) : (
        <View style={styles.completedList}>
          {completedSessions.map((session, index) => {
            const totalScore = getTotalScore(session.score) ?? 0
            const template = resolveCaseTemplate(
              session.case_templates as CaseTemplateSummary | CaseTemplateSummary[] | null,
            )
            return (
              <TouchableOpacity
                key={session.id}
                style={[styles.completedCard, index < completedSessions.length - 1 && styles.completedBorder]}
                onPress={() => router.push(`/case/${session.id}/score`)}
                activeOpacity={0.7}
              >
                <Text style={styles.completedIndex}>{String(index + 1).padStart(2, '0')}</Text>
                <View style={styles.completedContent}>
                  <Text style={styles.completedTitle} numberOfLines={1}>
                    {buildLearnerSafeCaseTitle(template?.chief_complaint)}
                  </Text>
                  <Text style={styles.completedTime}>
                    {session.completed_at ? new Date(session.completed_at).toLocaleDateString('zh-CN') : ''}
                  </Text>
                </View>
                <Text style={[styles.scoreText, { color: getMasteryColor(totalScore) }]}>{totalScore}</Text>
                <Ionicons name="chevron-forward" size={15} color={Colors.neutral[400]} />
              </TouchableOpacity>
            )
          })}
        </View>
      )}

      <Modal
        transparent
        animationType="fade"
        visible={pendingChiefComplaint !== null}
        onRequestClose={() => setPendingChiefComplaint(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.disclaimerCard}>
            <View style={styles.disclaimerTop}>
              <Text style={styles.disclaimerNumber}>01</Text>
              <View style={styles.disclaimerIconWrap}>
                <Ionicons name="shield-checkmark-outline" size={26} color={Colors.primary[700]} />
              </View>
            </View>
            <Text style={styles.disclaimerTitle}>学习用途声明</Text>
            <Text style={styles.disclaimerText}>
              MedLearn 是医学教育训练工具，不提供医疗建议。AI 生成内容可能不准确，不能用于真实患者诊断或治疗。
            </Text>
            <Text style={styles.disclaimerText}>
              请不要输入真实患者姓名、联系方式、病历号或其他可识别信息。
            </Text>
            <View style={styles.disclaimerActions}>
              <TouchableOpacity
                style={styles.disclaimerSecondaryButton}
                onPress={() => setPendingChiefComplaint(null)}
              >
                <Text style={styles.disclaimerSecondaryText}>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.disclaimerPrimaryButton} onPress={handleAcceptDisclaimer}>
                <Text style={styles.disclaimerPrimaryText}>我已了解</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    paddingHorizontal: Layout.screenPaddingX,
    // paddingBottom 由 inline（FLOATING_TAB_BAR_BASE_HEIGHT + insets.bottom + Spacing.lg）提供。
  },
  pageIntro: {
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.md,
  },
  pageIntroTitle: {
    ...Typography.titleLarge,
    fontFamily: FontFamily.sans,
    color: Colors.textPrimary,
  },
  pageIntroText: {
    fontSize: 15,
    lineHeight: 24,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
    maxWidth: 340,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    ...Typography.titleLarge,
    fontFamily: FontFamily.sans,
    color: Colors.textPrimary,
  },
  sectionMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  modeSwitch: {
    minHeight: 46,
    flexDirection: 'row',
    padding: 3,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surfaceVariant,
    marginBottom: Spacing.md,
  },
  modeButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: BorderRadius.full,
  },
  modeButtonActive: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modeButtonText: {
    ...Typography.labelLarge,
    color: Colors.textTertiary,
    fontWeight: '600',
  },
  modeButtonTextActive: {
    color: Colors.primary[700],
  },
  cardGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  examModeCard: {
    flexDirection: 'row',
    gap: Spacing.md,
    padding: Layout.cardPadding,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  examModeIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
  },
  examModeCopy: {
    flex: 1,
  },
  examModeTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  examModeText: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    marginTop: Spacing.xs,
    lineHeight: 19,
  },
  examModeAction: {
    alignSelf: 'flex-start',
    minHeight: 42,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[700],
    marginTop: Spacing.md,
  },
  examModeActionText: {
    ...Typography.labelMedium,
    color: Colors.surface,
    fontWeight: '600',
  },
  caseCard: {
    width: '48.5%' as any,
    minHeight: 108,
    backgroundColor: Colors.surface,
    padding: Layout.cardPadding,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  caseIconWrap: {
    width: Layout.iconWrap,
    height: Layout.iconWrap,
    borderRadius: Layout.iconWrap / 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
    // 收敛：统一使用 primarySoft，不再每个症状一种彩色，避免变成彩色 dashboard。
    backgroundColor: Colors.primary[50],
  },
  caseTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  caseSubtitle: {
    ...Typography.labelSmall,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  difficultyHint: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '600',
    marginTop: Spacing.xs,
  },
  loadingOverlay: {
    position: 'absolute',
    inset: 0,
    backgroundColor: 'rgba(255,253,249,0.78)',
    borderRadius: BorderRadius.xl,
    alignItems: 'center',
    justifyContent: 'center',
  },
  historyHeader: {
    marginTop: Spacing['2xl'],
  },
  historyBackLink: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  historyBackText: {
    ...Typography.labelLarge,
    color: Colors.primary[700],
    fontWeight: '600',
  },
  emptyCard: {
    minHeight: 120,
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'flex-start',
  },
  emptyTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  emptySubtitle: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    lineHeight: 19,
    marginTop: Spacing.xs,
    maxWidth: 280,
  },
  completedList: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.base,
  },
  completedCard: {
    minHeight: Layout.listRowHeightCompact,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  completedBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  completedIndex: {
    width: 22,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '400',
    color: Colors.textTertiary,
    fontFamily: FontFamily.sans,
    fontVariant: ['tabular-nums'],
  },
  completedContent: {
    flex: 1,
  },
  completedTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
    fontFamily: FontFamily.sans,
  },
  completedTime: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  scoreText: {
    ...Typography.numberMedium,
    fontFamily: FontFamily.sans,
    fontVariant: ['tabular-nums'],
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(13, 31, 27, 0.68)',
    justifyContent: 'center',
    padding: Spacing.lg,
  },
  disclaimerCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius['2xl'],
    padding: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  disclaimerTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.xl,
  },
  disclaimerNumber: {
    fontSize: 44,
    lineHeight: 48,
    fontWeight: '300',
    color: Colors.neutral[300],
  },
  disclaimerIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
  },
  disclaimerTitle: {
    ...Typography.titleLarge,
    fontFamily: FontFamily.sans,
    fontSize: 24,
    color: Colors.textPrimary,
    marginBottom: Spacing.md,
  },
  disclaimerText: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    lineHeight: 22,
    marginBottom: Spacing.sm,
  },
  disclaimerActions: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: Spacing.lg,
  },
  disclaimerSecondaryButton: {
    flex: 1,
    minHeight: 48,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disclaimerSecondaryText: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
  },
  disclaimerPrimaryButton: {
    flex: 1,
    minHeight: 48,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[700],
    alignItems: 'center',
    justifyContent: 'center',
  },
  disclaimerPrimaryText: {
    ...Typography.labelMedium,
    color: Colors.surface,
    fontWeight: '600',
  },
})

import { useEffect, useState } from 'react'
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert, ActivityIndicator, Modal } from 'react-native'
import { useLocalSearchParams, useNavigation, useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { supabase } from '@/lib/supabase'
import { caseEngine } from '@/services/case-engine'
import {
  getDifficultyLabel,
  recommendStretchDifficulty,
  type CaseDifficulty,
} from '@/utils/learningChallenge'
import { Colors, Typography, Spacing, BorderRadius, Shadows, getMasteryColor } from '@/constants/theme'
import { CHIEF_COMPLAINTS } from '@/constants/vindicate'

const COMPLAINT_META: Record<string, {
  icon: keyof typeof Ionicons.glyphMap
  cue: string
  tint: string
}> = {
  chest_pain: { icon: 'heart-outline', cue: '心血管 · 呼吸 · 消化', tint: '#F4E3DE' },
  dyspnea: { icon: 'cloud-outline', cue: '气道 · 肺循环', tint: '#E2EFF0' },
  abdominal_pain: { icon: 'body-outline', cue: '定位 · 性质 · 伴随症状', tint: '#EFE8D7' },
  fever: { icon: 'thermometer-outline', cue: '感染 · 炎症 · 肿瘤', tint: '#F2E3D7' },
  ams: { icon: 'flash-outline', cue: '神经 · 代谢 · 中毒', tint: '#E7E4EF' },
}

export default function CasesScreen() {
  const router = useRouter()
  const navigation = useNavigation()
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
      return data ?? []
    },
  })

  const getRecommendedDifficulty = (chiefComplaint: string): CaseDifficulty => {
    const latestSession = completedSessions.find((session) => {
      const template = session.case_templates as any
      return template?.chief_complaint === chiefComplaint
    })
    const score = (latestSession?.score as any)?.totalScore
    return recommendStretchDifficulty(typeof score === 'number' ? score : null)
  }

  const handleStartCase = async (chiefComplaint: string) => {
    if (!user) {
      Alert.alert('提示', '请先登录')
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
      Alert.alert('提示', '免责声明记录保存失败，下次进入时可能再次提示。')
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
        Alert.alert('提示', '该主诉下暂无可用病例')
        return
      }

      const selected = cases.find((item) => item.difficulty === recommendedDifficulty) || cases[0]
      const { sessionId } = await caseEngine.startCase(selected.id, userId)
      router.push(`/case/${sessionId}/chat`)
    } catch (e: any) {
      Alert.alert('错误', e.message || '启动病例失败')
    } finally {
      setLoading(null)
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      {!showHistoryFirst && (
        <>
          <View style={styles.pageIntro}>
            <Text style={styles.pageIntroTitle}>从一个主诉开始</Text>
            <Text style={styles.pageIntroText}>
              系统随机生成病例。你负责收集线索、提出诊断，并解释每一步判断。
            </Text>
          </View>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>选择主诉</Text>
            <Text style={styles.sectionMeta}>随机病例</Text>
          </View>

          <View style={styles.cardGrid}>
        {CHIEF_COMPLAINTS.map((complaint, index) => {
          const meta = COMPLAINT_META[complaint.id]
          const isFeatured = index === 0
          const recommendedDifficulty = getRecommendedDifficulty(complaint.id)
          return (
            <TouchableOpacity
              key={complaint.id}
              style={[styles.caseCard, isFeatured && styles.caseCardFeatured]}
              onPress={() => handleStartCase(complaint.id)}
              disabled={loading !== null}
              activeOpacity={0.75}
            >
              <View style={[
                styles.caseIconWrap,
                isFeatured && styles.caseIconFeatured,
                { backgroundColor: meta.tint },
              ]}>
                <Ionicons name={meta.icon} size={isFeatured ? 26 : 22} color={Colors.ink} />
              </View>
              <View style={isFeatured ? styles.caseFeaturedCopy : undefined}>
                <Text style={[styles.caseTitle, isFeatured && styles.caseTitleFeatured]}>{complaint.label}</Text>
                <Text style={styles.caseSubtitle} numberOfLines={1}>{meta.cue}</Text>
                <Text style={styles.difficultyHint}>
                  建议 · {getDifficultyLabel(recommendedDifficulty)}
                </Text>
              </View>
              {isFeatured && (
                <View style={styles.startMark}>
                  <Ionicons name="arrow-forward" size={18} color="#FFFDF9" />
                </View>
              )}
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
      )}

      <View style={[styles.sectionHeader, !showHistoryFirst && styles.historyHeader]}>
        <Text style={styles.sectionTitle}>病例记录</Text>
        <Text style={styles.sectionMeta}>{completedSessions.length} 次完成</Text>
      </View>

      {completedSessions.length === 0 ? (
        <View style={styles.emptyCard}>
          <View style={styles.emptyTop}>
            <Text style={styles.emptyNumber}>00</Text>
            <Ionicons name="clipboard-outline" size={26} color={Colors.primary[700]} />
          </View>
          <Text style={styles.emptyTitle}>还没有病例记录</Text>
          <Text style={styles.emptySubtitle}>完成第一次模拟后，这里会保存得分与结构化复盘。</Text>
        </View>
      ) : (
        <View style={styles.completedList}>
          {completedSessions.map((session, index) => {
            const score = session.score as any
            const template = session.case_templates as any
            const totalScore = score?.totalScore ?? 0
            return (
              <TouchableOpacity
                key={session.id}
                style={[styles.completedCard, index < completedSessions.length - 1 && styles.completedBorder]}
                onPress={() => router.push(`/case/${session.id}/score`)}
                activeOpacity={0.7}
              >
                <Text style={styles.completedIndex}>{String(index + 1).padStart(2, '0')}</Text>
                <View style={styles.completedContent}>
                  <Text style={styles.completedTitle} numberOfLines={1}>{template?.title || session.case_id}</Text>
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
              Medlearn 是医学教育训练工具，不提供医疗建议。AI 生成内容可能不准确，不能用于真实患者诊断或治疗。
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
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing['3xl'],
  },
  pageIntro: {
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.lg,
  },
  pageIntroTitle: {
    ...Typography.titleLarge,
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
    color: Colors.textPrimary,
  },
  sectionMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  cardGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  caseCard: {
    width: '48.5%' as any,
    minHeight: 142,
    backgroundColor: Colors.surface,
    padding: Spacing.base,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  caseCardFeatured: {
    width: '100%',
    minHeight: 94,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E7DCC9',
    borderColor: '#E7DCC9',
  },
  caseIconWrap: {
    width: 46,
    height: 46,
    borderRadius: 23,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.lg,
  },
  caseIconFeatured: {
    marginBottom: 0,
  },
  caseFeaturedCopy: {
    flex: 1,
    marginLeft: Spacing.md,
  },
  caseTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  caseTitleFeatured: {
    fontSize: 18,
  },
  caseSubtitle: {
    ...Typography.labelSmall,
    color: Colors.textSecondary,
    marginTop: 4,
  },
  difficultyHint: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '700',
    marginTop: Spacing.sm,
  },
  startMark: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.ink,
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
  emptyCard: {
    minHeight: 168,
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  emptyTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.xl,
  },
  emptyNumber: {
    fontSize: 42,
    lineHeight: 46,
    fontWeight: '300',
    color: Colors.neutral[200],
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
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  completedBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  completedIndex: {
    width: 22,
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textTertiary,
  },
  completedContent: {
    flex: 1,
  },
  completedTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  completedTime: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  scoreText: {
    ...Typography.titleSmall,
    fontWeight: '800',
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
    ...Shadows.level3,
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
    color: Colors.neutral[200],
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
    backgroundColor: Colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disclaimerPrimaryText: {
    ...Typography.labelMedium,
    color: '#FFFDF9',
  },
})

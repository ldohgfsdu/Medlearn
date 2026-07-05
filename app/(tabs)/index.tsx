import { useEffect, useState } from 'react'
import {
  ActivityIndicator,
  Text,
  TextInput,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native'
import { type Href, useRouter } from 'expo-router'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '@/hooks/useAuth'
import { useHomeStats, useKnowledgeLibraryStats, useRecentSessions } from '@/hooks/useKnowledge'
import {
  loadWrongQuestionRecords,
  locateWrongQuestion,
  saveWrongQuestionRecord,
} from '@/services/wrongQuestionService'
import type { WrongQuestionCandidate } from '@/utils/wrongQuestionIntake'
import { Colors, Typography, Spacing, BorderRadius, FontFamily } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { FLOATING_TAB_BAR_BASE_HEIGHT } from './_layout'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  return `${Math.floor(hours / 24)} 天前`
}

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

const KNOWLEDGE_ITEM = {
  title: '电子教材',
  subtitle: '按教材目录进入章节，查看知识点、证据和页码范围',
  icon: 'book-outline' as const,
  route: '/textbook' as Href,
}

const TRAIN_ITEMS = [
  {
    title: '开始病例',
    subtitle: '从主诉进入问诊、查体、检查和决策',
    icon: 'pulse-outline' as const,
    route: '/(tabs)/cases' as const,
  },
  {
    title: '病例复盘',
    subtitle: '查看已完成病例的评分与优先改进项',
    icon: 'document-text-outline' as const,
    route: { pathname: '/(tabs)/cases', params: { section: 'history' } } as const,
  },
  {
    title: '学习报告',
    subtitle: '查看累计病例、活跃学习日与表现概览',
    icon: 'analytics-outline' as const,
    route: '/(tabs)/analytics' as const,
  },
]

export default function HomeScreen() {
  const router = useRouter()
  const { user } = useAuth()
  const insets = useSafeAreaInsets()
  const nickname = user?.user_metadata?.nickname || '同学'
  const { data: stats } = useHomeStats(user?.id)
  const { data: libraryStats } = useKnowledgeLibraryStats()
  const { data: recentSessions } = useRecentSessions(user?.id)
  const [wrongQuestionText, setWrongQuestionText] = useState('')
  const [wrongQuestionCandidates, setWrongQuestionCandidates] = useState<WrongQuestionCandidate[]>([])
  const [locatingWrongQuestion, setLocatingWrongQuestion] = useState(false)
  const [wrongQuestionError, setWrongQuestionError] = useState('')
  const [savedCandidateIds, setSavedCandidateIds] = useState<Record<string, boolean>>({})
  const [wrongQuestionExpanded, setWrongQuestionExpanded] = useState(false)

  const completedToday = stats?.completedToday ?? 0
  const dailyMinimumMet = completedToday > 0

  useEffect(() => {
    loadWrongQuestionRecords()
      .then((records) => {
        setSavedCandidateIds(Object.fromEntries(records.map((record) => [record.candidate.id, true])))
      })
      .catch(() => setSavedCandidateIds({}))
  }, [])

  const openWrongQuestionCandidate = (candidate: WrongQuestionCandidate) => {
    router.push({
      pathname: '/textbook/[sectionId]/unit/[unitId]',
      params: {
        sectionId: candidate.sectionId,
        unitId: candidate.unitId,
        targetItemId: candidate.itemId || candidate.id.split(':').pop(),
        from: 'wrong-question',
      },
    } as unknown as Href)
  }

  const runWrongQuestionLocate = async () => {
    const question = wrongQuestionText.trim()
    if (question.length < 4 || locatingWrongQuestion) return

    setLocatingWrongQuestion(true)
    setWrongQuestionError('')
    try {
      const candidates = await locateWrongQuestion(question)
      setWrongQuestionCandidates(candidates)
      if (candidates.length === 0) {
        setWrongQuestionError('没有找到带教材证据和页码的候选位置，请换成更接近题干的关键词。')
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      setWrongQuestionError(message || '错题定位暂时不可用，请稍后重试。')
    } finally {
      setLocatingWrongQuestion(false)
    }
  }

  const saveWrongQuestionCandidate = async (candidate: WrongQuestionCandidate) => {
    const question = wrongQuestionText.trim()
    if (!question) return
    const records = await saveWrongQuestionRecord(question, candidate)
    setSavedCandidateIds(Object.fromEntries(records.map((record) => [record.candidate.id, true])))
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[
        styles.content,
        {
          paddingTop: insets.top + Spacing.lg,
          // 为浮动 Pill TabBar 留出 safe area padding，避免末尾内容被遮挡。
          paddingBottom: FLOATING_TAB_BAR_BASE_HEIGHT + insets.bottom + Spacing.lg,
        },
      ]}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.brandRow}>
        <View>
          <Text style={styles.brand}>MedLearn</Text>
        </View>
        <TouchableOpacity
          style={styles.avatarButton}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          onPress={() => router.push('/(tabs)/profile')}
        >
          <Text style={styles.avatarText}>{nickname.slice(0, 1)}</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.greetingRow}>
        <Text style={styles.greeting}>{getGreeting()}，{nickname}</Text>
        <View style={[styles.dailyState, dailyMinimumMet && styles.dailyStateDone]}>
          <Ionicons
            name={dailyMinimumMet ? 'checkmark-circle' : 'ellipse-outline'}
            size={14}
            color={dailyMinimumMet ? Colors.success : Colors.textTertiary}
          />
          <Text style={[styles.dailyStateText, dailyMinimumMet && styles.dailyStateTextDone]}>
            {dailyMinimumMet ? '已记录' : '待开始'}
          </Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.hero}
        activeOpacity={0.9}
        onPress={() => router.push('/(tabs)/cases')}
      >
        <View style={styles.heroTopRow}>
          <View style={styles.heroLabel}>
            <View style={styles.heroLabelDot} />
            <Text style={styles.heroLabelText}>{dailyMinimumMet ? '今日已完成' : '今日下限'}</Text>
          </View>
          {dailyMinimumMet ? (
            <Ionicons name="checkmark-circle" size={28} color={Colors.success} />
          ) : null}
        </View>
        <Text style={styles.heroTitle}>
          {dailyMinimumMet ? <>今天已经完成。{'\n'}继续练，是额外收获</> : <>只做一个病例，{'\n'}先让学习开始</>}
        </Text>
        <Text style={styles.heroSubtitle}>
          {dailyMinimumMet
            ? '没有需要维持的连续纪录，也没有必须完成的上限。'
            : '问诊、检查、诊断与治疗，结束后留下真实学习记录。'}
        </Text>
        <View style={styles.heroActionRow}>
          <View style={styles.heroButton}>
            <Text style={styles.heroButtonText}>{dailyMinimumMet ? '再练一个' : '完成今日下限'}</Text>
            <Ionicons name="arrow-forward" size={16} color={Colors.ink} />
          </View>
          <Text style={styles.heroMeta}>无上限 · 可随时结束</Text>
        </View>
      </TouchableOpacity>

      {/* 错题定位 - 可折叠 */}
      <TouchableOpacity
        style={styles.wrongQuestionToggle}
        activeOpacity={0.65}
        onPress={() => setWrongQuestionExpanded((v) => !v)}
      >
        <View style={styles.wrongQuestionToggleLeft}>
          <Ionicons name="locate-outline" size={18} color={Colors.primary[700]} />
          <Text style={styles.wrongQuestionToggleTitle}>错题定位</Text>
        </View>
        <View style={styles.wrongQuestionToggleRight}>
          <Text style={styles.wrongQuestionToggleHint}>粘贴题干定位教材证据</Text>
          <Ionicons
            name={wrongQuestionExpanded ? 'chevron-up' : 'chevron-down'}
            size={16}
            color={Colors.neutral[400]}
          />
        </View>
      </TouchableOpacity>

      {wrongQuestionExpanded ? (
        <View style={styles.wrongQuestionPanel}>
          <TextInput
            style={styles.wrongQuestionInput}
            testID="home-wrong-question-input"
            value={wrongQuestionText}
            onChangeText={setWrongQuestionText}
            placeholder="例如：肺炎链球菌肺炎的诊断依据、治疗或鉴别点"
            placeholderTextColor={Colors.textTertiary}
            multiline
            maxLength={500}
            textAlignVertical="top"
          />
          <TouchableOpacity
            style={[
              styles.locateButton,
              (wrongQuestionText.trim().length < 4 || locatingWrongQuestion) && styles.locateButtonDisabled,
            ]}
            testID="home-wrong-question-locate-button"
            activeOpacity={0.78}
            disabled={wrongQuestionText.trim().length < 4 || locatingWrongQuestion}
            onPress={runWrongQuestionLocate}
          >
            {locatingWrongQuestion ? (
              <ActivityIndicator size="small" color={Colors.surface} />
            ) : (
              <Ionicons name="search-outline" size={17} color={Colors.surface} />
            )}
            <Text style={styles.locateButtonText}>
              {locatingWrongQuestion ? '正在定位' : '定位教材证据'}
            </Text>
          </TouchableOpacity>
          {wrongQuestionError ? <Text style={styles.wrongQuestionError}>{wrongQuestionError}</Text> : null}
          {wrongQuestionCandidates.length > 0 ? (
            <View style={styles.candidateList}>
              {wrongQuestionCandidates.slice(0, 2).map((candidate, index) => (
                <View
                  key={candidate.id}
                  style={styles.candidateRow}
                  testID={index === 0 ? 'home-wrong-question-candidate' : undefined}
                >
                  <View style={styles.candidateCopy}>
                    <Text style={styles.candidateTitle} numberOfLines={2}>
                      {candidate.itemTitle || candidate.groupTitle}
                    </Text>
                    <Text style={styles.candidateMeta} numberOfLines={1}>
                      {candidate.unitTitle} · {candidate.pageLabel}
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={styles.candidateSaveButton}
                    activeOpacity={0.72}
                    testID={index === 0 ? 'wrong-question-save-candidate-button' : `wrong-question-save-candidate-button-${index}`}
                    onPress={() => saveWrongQuestionCandidate(candidate)}
                  >
                    <Ionicons
                      name={savedCandidateIds[candidate.id] ? 'checkmark-circle' : 'add-circle-outline'}
                      size={17}
                      color={savedCandidateIds[candidate.id] ? Colors.success : Colors.primary[700]}
                    />
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.candidateOpenButton}
                    activeOpacity={0.78}
                    testID={index === 0 ? 'wrong-question-open-candidate-button' : `wrong-question-open-candidate-button-${index}`}
                    onPress={() => openWrongQuestionCandidate(candidate)}
                  >
                    <Text style={styles.candidateOpenText}>打开</Text>
                  </TouchableOpacity>
                </View>
              ))}
            </View>
          ) : null}
          <TouchableOpacity
            style={styles.queueInlineButton}
            activeOpacity={0.72}
            onPress={() => router.push('/wrong-questions' as Href)}
          >
            <Text style={styles.queueInlineText}>查看弱点队列</Text>
            <Ionicons name="arrow-forward" size={14} color={Colors.primary[700]} />
          </TouchableOpacity>
        </View>
      ) : null}

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>学习工具</Text>
        <Text style={styles.sectionCount}>
          {libraryStats?.totalNodes ?? 0} 个知识点
        </Text>
      </View>

      {/* 知识浏览 */}
      <View style={styles.toolList}>
        <TouchableOpacity
          style={styles.toolRow}
          activeOpacity={0.65}
          onPress={() => router.push(KNOWLEDGE_ITEM.route)}
        >
          <View style={[styles.toolIcon, styles.toolIconInfo]}>
            <Ionicons name={KNOWLEDGE_ITEM.icon} size={21} color={Colors.info} />
          </View>
          <View style={styles.toolCopy}>
            <Text style={styles.toolTitle}>{KNOWLEDGE_ITEM.title}</Text>
            <Text style={styles.toolSubtitle}>
              {libraryStats?.totalNodes
                ? `${libraryStats.totalNodes} 个知识点 · 按篇章展开`
                : KNOWLEDGE_ITEM.subtitle}
            </Text>
          </View>
          <View style={styles.toolArrow}>
            <Ionicons name="arrow-forward" size={17} color={Colors.neutral[400]} />
          </View>
        </TouchableOpacity>
      </View>

      {/* 训练操作 */}
      <Text style={styles.subSectionLabel}>训练</Text>
      <View style={styles.toolList}>
        {TRAIN_ITEMS.map((item, index) => (
          <TouchableOpacity
            key={item.title}
            style={[styles.toolRow, index < TRAIN_ITEMS.length - 1 && styles.toolRowBorder]}
            activeOpacity={0.65}
            onPress={() => router.push(item.route)}
          >
            <View style={styles.toolIcon}>
              <Ionicons name={item.icon} size={21} color={Colors.primary[700]} />
            </View>
            <View style={styles.toolCopy}>
              <Text style={styles.toolTitle}>{item.title}</Text>
              <Text style={styles.toolSubtitle}>{item.subtitle}</Text>
            </View>
            <View style={styles.toolArrow}>
              <Ionicons name="arrow-forward" size={17} color={Colors.neutral[400]} />
            </View>
          </TouchableOpacity>
        ))}
      </View>

      {recentSessions && recentSessions.length > 0 && (
        <>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>最近复盘</Text>
            <TouchableOpacity onPress={() => router.push('/(tabs)/cases')}>
              <Text style={styles.seeAll}>全部记录</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.recentList}>
            {recentSessions.map((session, index) => (
              <TouchableOpacity
                key={session.id}
                style={[styles.reviewItem, index < recentSessions.length - 1 && styles.reviewItemBorder]}
                activeOpacity={0.7}
                onPress={() => router.push(`/case/${session.id}/score`)}
              >
                <View style={styles.reviewMark}>
                  <Ionicons name="document-text-outline" size={18} color={Colors.primary[700]} />
                </View>
                <View style={styles.reviewContent}>
                  <Text style={styles.reviewText} numberOfLines={1}>{session.title}</Text>
                  <Text style={styles.reviewTime}>{timeAgo(session.completedAt)}</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={Colors.neutral[400]} />
              </TouchableOpacity>
            ))}
          </View>
        </>
      )}
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
    // paddingBottom 由 inline（FLOATING_TAB_BAR_BASE_HEIGHT + insets.bottom + Spacing.md）提供，
    // 为浮动 TabBar 留出 safe area。
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Layout.sectionGap,
  },
  brand: {
    fontSize: 13,
    lineHeight: 16,
    fontWeight: '600',
    color: Colors.ink,
    fontFamily: FontFamily.sans,
  },
  avatarButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.ink,
  },
  avatarText: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.surface,
  },
  greetingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Layout.sectionGap,
  },
  greeting: {
    // 问候语降级：让 Hero 成为首屏唯一视觉焦点，问候语退为次级信息。
    fontSize: 18,
    lineHeight: 24,
    fontWeight: '600',
    color: Colors.textPrimary,
    fontFamily: FontFamily.sans,
  },
  dailyState: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 5,
    paddingHorizontal: Spacing.sm,
    height: 30,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  dailyStateDone: {
    borderColor: Colors.primary[200],
    backgroundColor: Colors.primary[50],
  },
  dailyStateText: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  dailyStateTextDone: {
    color: Colors.primary[700],
    fontWeight: '600',
  },
  wrongQuestionToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 48,
    paddingHorizontal: Spacing.base,
    backgroundColor: Colors.surface,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  wrongQuestionToggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  wrongQuestionToggleTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  wrongQuestionToggleRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  wrongQuestionToggleHint: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  hero: {
    overflow: 'hidden',
    backgroundColor: Colors.surface,
    borderRadius: Layout.cardRadius,
    padding: Layout.heroPadding,
    // Hero 与下方模块间距大于普通 sectionGap，强化唯一焦点感
    marginBottom: Layout.sectionGap + Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  wrongQuestionPanel: {
    gap: Spacing.md,
    padding: Spacing.base,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    // 展开面板不使用提示态青绿边框，统一用 border；只有输入框 focus 才用 ink
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    marginBottom: Layout.sectionGap,
  },
  wrongQuestionInput: {
    minHeight: 78,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.inputBg,
    color: Colors.textPrimary,
    ...Typography.bodyMedium,
  },
  locateButton: {
    minHeight: 46,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[700],
  },
  locateButtonDisabled: {
    opacity: 0.48,
  },
  locateButtonText: {
    ...Typography.labelLarge,
    color: Colors.surface,
    fontWeight: '600',
  },
  wrongQuestionError: {
    ...Typography.bodyMedium,
    color: Colors.error,
    lineHeight: 21,
  },
  candidateList: {
    gap: Spacing.sm,
  },
  candidateRow: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.sm,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.background,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  candidateCopy: {
    flex: 1,
    minWidth: 0,
  },
  candidateTitle: {
    ...Typography.titleSmall,
    fontFamily: FontFamily.serif,
    color: Colors.textPrimary,
  },
  candidateMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  candidateSaveButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  candidateOpenButton: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[700],
  },
  candidateOpenText: {
    ...Typography.labelMedium,
    color: Colors.surface,
    fontWeight: '600',
  },
  queueInlineButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
    minHeight: 44,
    paddingVertical: Spacing.sm,
  },
  queueInlineText: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
    fontWeight: '600',
  },
  heroTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heroLabel: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  heroLabelDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: Colors.accent,
  },
  heroLabelText: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
    fontFamily: FontFamily.sans,
  },
  heroTitle: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: '600',
    color: Colors.ink,
    marginTop: Spacing.md,
    fontFamily: FontFamily.sans,
  },
  heroSubtitle: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    fontFamily: FontFamily.sans,
    marginTop: Spacing.sm,
  },
  heroActionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
  },
  heroButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.accent,
    paddingHorizontal: Spacing.base,
    height: 44,
    borderRadius: BorderRadius.full,
  },
  heroButtonText: {
    ...Typography.labelLarge,
    color: Colors.ink,
    fontFamily: FontFamily.sans,
    fontWeight: '600',
  },
  heroMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    fontFamily: FontFamily.sans,
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
  sectionCount: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textTertiary,
  },
  toolList: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    paddingHorizontal: Layout.cardPadding,
    marginBottom: Spacing.sm,
  },
  toolRow: {
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.xs,
  },
  toolRowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  toolIcon: {
    width: Layout.iconWrap,
    height: Layout.iconWrap,
    borderRadius: Layout.iconWrap / 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
    marginRight: Spacing.sm,
  },
  toolIconInfo: {
    // 降饱和：从青蓝 rgba(52,124,145,0.08) 改为 primary[50] 灰绿，与墨绿主色统一
    backgroundColor: Colors.primary[50],
  },
  toolCopy: {
    flex: 1,
    minWidth: 0,
    paddingRight: Spacing.xs,
  },
  toolTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  toolSubtitle: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
    lineHeight: 21,
    marginTop: 2,
    flexShrink: 1,
  },
  toolArrow: {
    width: 28,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  seeAll: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
    minHeight: 44,
    paddingHorizontal: Spacing.xs,
    textAlignVertical: 'center',
  },
  subSectionLabel: {
    ...Typography.labelMedium,
    color: Colors.textTertiary,
    fontWeight: '500',
    marginBottom: Spacing.sm,
    marginTop: Spacing.sm,
  },
  recentList: {
    backgroundColor: Colors.surface,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Layout.cardPadding,
  },
  reviewItem: {
    minHeight: Layout.listRowHeightCompact,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  reviewItemBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  reviewMark: {
    width: Layout.iconWrapSm,
    height: Layout.iconWrapSm,
    borderRadius: Layout.iconWrapSm / 2,
    backgroundColor: Colors.primary[50],
    alignItems: 'center',
    justifyContent: 'center',
  },
  reviewContent: {
    flex: 1,
  },
  reviewText: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  reviewTime: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
})

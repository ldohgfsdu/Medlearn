import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native'
import { useRouter } from 'expo-router'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '@/hooks/useAuth'
import { useHomeStats, useKnowledgeLibraryStats, useRecentSessions } from '@/hooks/useKnowledge'
import { Colors, Typography, Spacing, BorderRadius, Shadows } from '@/constants/theme'

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
  index: '01',
  title: '知识地图',
  subtitle: '按教材目录浏览疾病、概念与结构化要点',
  icon: 'book-outline' as const,
  route: '/(tabs)/learn' as const,
}

const TRAIN_ITEMS = [
  {
    index: '02',
    title: '开始病例',
    subtitle: '从主诉进入问诊、查体、检查和决策',
    icon: 'pulse-outline' as const,
    route: '/(tabs)/cases' as const,
  },
  {
    index: '03',
    title: '病例复盘',
    subtitle: '查看已完成病例的评分与优先改进项',
    icon: 'document-text-outline' as const,
    route: { pathname: '/(tabs)/cases', params: { section: 'history' } } as const,
  },
  {
    index: '04',
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

  const completedToday = stats?.completedToday ?? 0
  const learningDays = stats?.learningDays ?? 0
  const completedCases = stats?.completedCases ?? 0
  const dailyMinimumMet = completedToday > 0

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={[styles.content, { paddingTop: insets.top + Spacing.lg }]}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.brandRow}>
        <View>
          <Text style={styles.brand}>MEDLEARN</Text>
          <Text style={styles.brandCaption}>Clinical Learning Studio</Text>
        </View>
        <TouchableOpacity style={styles.avatarButton} onPress={() => router.push('/(tabs)/profile')}>
          <Text style={styles.avatarText}>{nickname.slice(0, 1)}</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.greetingRow}>
        <View style={styles.greetingCopy}>
          <Text style={styles.greeting}>{getGreeting()}，{nickname}</Text>
          <Text style={styles.greetingSub}>今天只设一个下限：完成 1 个病例。做完就算完成，想继续就继续。</Text>
        </View>
        <View style={[styles.dailyState, dailyMinimumMet && styles.dailyStateDone]}>
          <Ionicons
            name={dailyMinimumMet ? 'checkmark-circle' : 'ellipse-outline'}
            size={16}
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
        <View style={styles.heroOrbLarge} />
        <View style={styles.heroOrbSmall} />
        <View style={styles.heroTopRow}>
          <View style={styles.heroLabel}>
            <View style={styles.heroLabelDot} />
            <Text style={styles.heroLabelText}>{dailyMinimumMet ? '今日已完成' : '今日下限'}</Text>
          </View>
          <Text style={styles.heroNumber}>{dailyMinimumMet ? '✓' : '01'}</Text>
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

      <View style={styles.sectionHeader}>
        <View>
          <Text style={styles.sectionEyebrow}>KNOWLEDGE LIBRARY</Text>
          <Text style={styles.sectionTitle}>知识库</Text>
        </View>
        <Text style={styles.sectionCount}>
          {String(libraryStats?.totalNodes ?? 0).padStart(2, '0')}
        </Text>
      </View>

      <View style={styles.toolList}>
        <TouchableOpacity
          style={[styles.toolRow, styles.toolRowBorder]}
          activeOpacity={0.65}
          onPress={() => router.push(KNOWLEDGE_ITEM.route)}
        >
          <Text style={styles.toolIndex}>{KNOWLEDGE_ITEM.index}</Text>
          <View style={styles.toolIcon}>
            <Ionicons name={KNOWLEDGE_ITEM.icon} size={21} color={Colors.primary[700]} />
          </View>
          <View style={styles.toolCopy}>
            <Text style={styles.toolTitle}>{KNOWLEDGE_ITEM.title}</Text>
            <Text style={styles.toolSubtitle}>
              {libraryStats?.totalNodes
                ? `已收录 ${libraryStats.totalNodes} 个知识点，按篇章展开阅读`
                : KNOWLEDGE_ITEM.subtitle}
            </Text>
          </View>
          <Ionicons name="arrow-forward" size={17} color={Colors.neutral[400]} />
        </TouchableOpacity>
        {TRAIN_ITEMS.map((item, index) => (
          <TouchableOpacity
            key={item.title}
            style={[styles.toolRow, index < TRAIN_ITEMS.length - 1 ? styles.toolRowBorder : undefined]}
            activeOpacity={0.65}
            onPress={() => router.push(item.route)}
          >
            <Text style={styles.toolIndex}>{item.index}</Text>
            <View style={styles.toolIcon}>
              <Ionicons name={item.icon} size={21} color={Colors.primary[700]} />
            </View>
            <View style={styles.toolCopy}>
              <Text style={styles.toolTitle}>{item.title}</Text>
              <Text style={styles.toolSubtitle}>{item.subtitle}</Text>
            </View>
            <Ionicons name="arrow-forward" size={17} color={Colors.neutral[400]} />
          </TouchableOpacity>
        ))}
      </View>

      <View style={styles.dataStrip}>
        <TouchableOpacity style={styles.dataItem} onPress={() => router.push('/(tabs)/cases')}>
          <Text style={styles.dataValue}>{completedToday}</Text>
          <Text style={styles.dataLabel}>今日记录</Text>
        </TouchableOpacity>
        <View style={styles.dataDivider} />
        <TouchableOpacity style={styles.dataItem} onPress={() => router.push('/(tabs)/cases')}>
          <Text style={styles.dataValue}>{completedCases}</Text>
          <Text style={styles.dataLabel}>累计病例</Text>
        </TouchableOpacity>
        <View style={styles.dataDivider} />
        <TouchableOpacity style={styles.dataItem} onPress={() => router.push('/(tabs)/analytics')}>
          <Text style={styles.dataValue}>{learningDays}</Text>
          <Text style={styles.dataLabel}>学习日</Text>
        </TouchableOpacity>
      </View>

      {recentSessions && recentSessions.length > 0 && (
        <>
          <View style={styles.sectionHeader}>
            <View>
              <Text style={styles.sectionEyebrow}>RECENT REVIEW</Text>
              <Text style={styles.sectionTitle}>最近复盘</Text>
            </View>
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
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing['4xl'],
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing['2xl'],
  },
  brand: {
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '800',
    letterSpacing: 2.2,
    color: Colors.primary[700],
  },
  brandCaption: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
    letterSpacing: 0.5,
  },
  avatarButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.ink,
  },
  avatarText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#F7F0E5',
  },
  greetingRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: Spacing.lg,
  },
  greetingCopy: {
    flex: 1,
    paddingRight: Spacing.base,
  },
  greeting: {
    fontSize: 28,
    lineHeight: 35,
    fontWeight: '800',
    letterSpacing: -0.8,
    color: Colors.textPrimary,
  },
  greetingSub: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
    lineHeight: 21,
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
    fontWeight: '700',
  },
  hero: {
    minHeight: 292,
    overflow: 'hidden',
    backgroundColor: Colors.ink,
    borderRadius: BorderRadius['2xl'],
    padding: Spacing.xl,
    marginBottom: Spacing['2xl'],
    ...Shadows.level2,
  },
  heroOrbLarge: {
    position: 'absolute',
    width: 210,
    height: 210,
    borderRadius: 105,
    right: -80,
    top: -65,
    borderWidth: 1,
    borderColor: 'rgba(216, 235, 224, 0.16)',
  },
  heroOrbSmall: {
    position: 'absolute',
    width: 108,
    height: 108,
    borderRadius: 54,
    right: 28,
    bottom: -54,
    backgroundColor: 'rgba(226, 122, 87, 0.14)',
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
    color: '#D8EBE0',
    letterSpacing: 0.8,
  },
  heroNumber: {
    fontSize: 44,
    lineHeight: 48,
    fontWeight: '300',
    color: 'rgba(216, 235, 224, 0.2)',
  },
  heroTitle: {
    fontSize: 27,
    lineHeight: 36,
    fontWeight: '800',
    letterSpacing: -0.5,
    color: '#FFFDF9',
    marginTop: Spacing.lg,
  },
  heroSubtitle: {
    ...Typography.bodyMedium,
    lineHeight: 22,
    color: 'rgba(255, 253, 249, 0.66)',
    maxWidth: 300,
    marginTop: Spacing.md,
  },
  heroActionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 'auto',
    paddingTop: Spacing.xl,
  },
  heroButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: '#E7DCC9',
    paddingHorizontal: Spacing.base,
    height: 44,
    borderRadius: BorderRadius.full,
  },
  heroButtonText: {
    ...Typography.labelLarge,
    color: Colors.ink,
    fontWeight: '700',
  },
  heroMeta: {
    ...Typography.labelSmall,
    color: 'rgba(255, 253, 249, 0.52)',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  sectionEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '700',
    letterSpacing: 1.4,
    color: Colors.textTertiary,
    marginBottom: 3,
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
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
    marginBottom: Spacing.base,
  },
  toolRow: {
    minHeight: 82,
    flexDirection: 'row',
    alignItems: 'center',
  },
  toolRowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  toolIndex: {
    width: 28,
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textTertiary,
  },
  toolIcon: {
    width: 40,
    height: 40,
    borderRadius: BorderRadius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
    marginRight: Spacing.md,
  },
  toolCopy: {
    flex: 1,
  },
  toolTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  toolSubtitle: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  dataStrip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.lg,
    marginBottom: Spacing['2xl'],
  },
  dataItem: {
    flex: 1,
    alignItems: 'center',
  },
  dataDivider: {
    width: StyleSheet.hairlineWidth,
    height: 32,
    backgroundColor: Colors.border,
  },
  dataValue: {
    fontSize: 23,
    lineHeight: 28,
    fontWeight: '800',
    color: Colors.textPrimary,
  },
  dataLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 3,
  },
  seeAll: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
  },
  recentList: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.base,
  },
  reviewItem: {
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  reviewItemBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  reviewMark: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: Colors.primary[50],
    alignItems: 'center',
    justifyContent: 'center',
  },
  reviewContent: {
    flex: 1,
  },
  reviewText: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  reviewTime: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
})

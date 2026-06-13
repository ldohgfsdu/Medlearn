import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useRouter } from 'expo-router'
import { useAuth } from '@/hooks/useAuth'
import { useAnalyticsStats } from '@/hooks/useAnalyticsStats'
import { BorderRadius, Colors, Spacing, Typography, getMasteryColor } from '@/constants/theme'

export default function AnalyticsScreen() {
  const router = useRouter()
  const { user } = useAuth()
  const { data, isLoading } = useAnalyticsStats(user?.id)

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator color={Colors.primary[700]} />
        <Text style={styles.loadingText}>正在整理学习记录</Text>
      </View>
    )
  }

  const completedCases = data?.completedCases ?? 0
  const avgScore = data?.avgScore ?? 0
  const totalMinutes = data?.totalMinutes ?? 0
  const hasData = completedCases > 0

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <Text style={styles.heroEyebrow}>LEARNING RECORD</Text>
          <Text style={styles.heroIndex}>{hasData ? '01' : '00'}</Text>
        </View>
        <Text style={styles.heroTitle}>
          {hasData ? '先看趋势，\n再决定下一次练什么' : '完成一次病例，\n这里才开始有意义'}
        </Text>
        <Text style={styles.heroDescription}>
          {hasData
            ? '记录只用于发现稳定优势与重复盲点，不用来制造连续打卡压力。'
            : '报告不会填充虚构数据。完成病例后，这里会基于真实表现生成分析。'}
        </Text>
        <View style={styles.heroStats}>
          <View style={styles.heroStat}>
            <Text style={styles.heroValue}>{completedCases}</Text>
            <Text style={styles.heroLabel}>完成病例</Text>
          </View>
          <View style={styles.heroDivider} />
          <View style={styles.heroStat}>
            <Text style={styles.heroValue}>{avgScore}</Text>
            <Text style={styles.heroLabel}>平均分</Text>
          </View>
          <View style={styles.heroDivider} />
          <View style={styles.heroStat}>
            <Text style={styles.heroValue}>{totalMinutes}</Text>
            <Text style={styles.heroLabel}>学习分钟</Text>
          </View>
        </View>
      </View>

      {hasData ? (
        <>
          {data?.subjectScores && data.subjectScores.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <View>
                  <Text style={styles.sectionEyebrow}>BY SPECIALTY</Text>
                  <Text style={styles.sectionTitle}>知识维度</Text>
                </View>
                <Text style={styles.sectionCount}>{String(data.subjectScores.length).padStart(2, '0')}</Text>
              </View>
              <View style={styles.subjectList}>
                {data.subjectScores.map((item, index) => {
                  const color = getMasteryColor(item.score)
                  return (
                    <View
                      key={item.name}
                      style={[styles.subjectRow, index < data.subjectScores.length - 1 && styles.rowDivider]}
                    >
                      <Text style={styles.rowIndex}>{String(index + 1).padStart(2, '0')}</Text>
                      <View style={styles.subjectCopy}>
                        <View style={styles.subjectHeading}>
                          <Text style={styles.subjectName}>{item.name}</Text>
                          <Text style={[styles.subjectScore, { color }]}>{item.score}%</Text>
                        </View>
                        <View style={styles.progressTrack}>
                          <View style={[styles.progressFill, { width: `${Math.min(item.score, 100)}%`, backgroundColor: color }]} />
                        </View>
                      </View>
                    </View>
                  )
                })}
              </View>
            </View>
          )}

          {data?.reasoningMetrics && data.reasoningMetrics.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <View>
                  <Text style={styles.sectionEyebrow}>REASONING SIGNALS</Text>
                  <Text style={styles.sectionTitle}>推理维度</Text>
                </View>
                <Text style={styles.sectionCount}>{String(data.reasoningMetrics.length).padStart(2, '0')}</Text>
              </View>
              <View style={styles.metricList}>
                {data.reasoningMetrics.map((item, index) => (
                  <View
                    key={item.name}
                    style={[styles.metricRow, index < data.reasoningMetrics.length - 1 && styles.rowDivider]}
                  >
                    <Text style={styles.rowIndex}>{String(index + 1).padStart(2, '0')}</Text>
                    <Text style={styles.metricName}>{item.name}</Text>
                    <Text style={styles.metricValue}>{item.value}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}
        </>
      ) : (
        <View style={styles.emptyPanel}>
          <View style={styles.emptyMark}>
            <Ionicons name="analytics-outline" size={24} color={Colors.primary[700]} />
          </View>
          <Text style={styles.emptyTitle}>暂无学习数据</Text>
          <Text style={styles.emptyText}>完成第一个模拟病例后，真实得分与推理表现会显示在这里。</Text>
          <TouchableOpacity
            style={styles.emptyAction}
            activeOpacity={0.75}
            onPress={() => router.push('/(tabs)/cases')}
          >
            <Text style={styles.emptyActionText}>开始第一个病例</Text>
            <Ionicons name="arrow-forward" size={16} color="#FFFDF9" />
          </TouchableOpacity>
        </View>
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
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
    backgroundColor: Colors.background,
  },
  loadingText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
  },
  hero: {
    minHeight: 300,
    backgroundColor: Colors.ink,
    borderRadius: BorderRadius['2xl'],
    padding: Spacing.xl,
    marginBottom: Spacing['2xl'],
  },
  heroTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heroEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '800',
    letterSpacing: 1.5,
    color: '#9DC8B9',
  },
  heroIndex: {
    fontSize: 34,
    lineHeight: 38,
    fontWeight: '300',
    color: 'rgba(231, 220, 201, 0.28)',
  },
  heroTitle: {
    fontSize: 28,
    lineHeight: 36,
    fontWeight: '800',
    letterSpacing: -0.7,
    color: '#FFFDF9',
    marginTop: Spacing.md,
  },
  heroDescription: {
    ...Typography.bodyMedium,
    lineHeight: 22,
    color: 'rgba(255, 253, 249, 0.62)',
    maxWidth: 330,
    marginTop: Spacing.sm,
  },
  heroStats: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 'auto',
    paddingTop: Spacing.xl,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(255, 253, 249, 0.18)',
  },
  heroStat: {
    flex: 1,
  },
  heroDivider: {
    width: StyleSheet.hairlineWidth,
    height: 34,
    backgroundColor: 'rgba(255, 253, 249, 0.18)',
    marginHorizontal: Spacing.md,
  },
  heroValue: {
    fontSize: 23,
    lineHeight: 28,
    fontWeight: '800',
    color: '#FFFDF9',
  },
  heroLabel: {
    ...Typography.labelSmall,
    color: 'rgba(255, 253, 249, 0.5)',
    marginTop: 3,
  },
  section: {
    marginBottom: Spacing['2xl'],
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
    color: Colors.textTertiary,
  },
  subjectList: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
  },
  subjectRow: {
    minHeight: 78,
    flexDirection: 'row',
    alignItems: 'center',
  },
  rowDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  rowIndex: {
    width: 30,
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textTertiary,
  },
  subjectCopy: {
    flex: 1,
  },
  subjectHeading: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  subjectName: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  subjectScore: {
    ...Typography.labelMedium,
    fontWeight: '800',
  },
  progressTrack: {
    height: 4,
    overflow: 'hidden',
    backgroundColor: Colors.neutral[100],
    borderRadius: BorderRadius.full,
  },
  progressFill: {
    height: '100%',
    borderRadius: BorderRadius.full,
  },
  metricList: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
  },
  metricRow: {
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
  },
  metricName: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  metricValue: {
    fontSize: 18,
    lineHeight: 24,
    fontWeight: '800',
    color: Colors.primary[700],
  },
  emptyPanel: {
    minHeight: 190,
    justifyContent: 'flex-end',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
  },
  emptyMark: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
    marginBottom: Spacing.xl,
  },
  emptyTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  emptyText: {
    ...Typography.bodySmall,
    lineHeight: 19,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
    maxWidth: 300,
  },
  emptyAction: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    marginTop: Spacing.lg,
    paddingHorizontal: Spacing.xl,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.ink,
  },
  emptyActionText: {
    ...Typography.labelLarge,
    color: '#FFFDF9',
  },
})

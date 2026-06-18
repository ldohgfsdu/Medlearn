import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useRouter } from 'expo-router'
import { useAuth } from '@/hooks/useAuth'
import { useAnalyticsStats } from '@/hooks/useAnalyticsStats'
import { BorderRadius, Colors, Spacing, Typography, getMasteryColor } from '@/constants/theme'
import { Layout } from '@/constants/layout'

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
      <View style={styles.summaryCard}>
        <Text style={styles.summaryTitle}>
          {hasData ? '学习记录概览' : '还没有学习记录'}
        </Text>
        <Text style={styles.summaryDescription}>
          {hasData
            ? '记录只用于发现稳定优势与重复盲点，不用来制造连续打卡压力。'
            : '完成病例后，这里会基于真实表现生成分析，不会填充虚构数据。'}
        </Text>
        <View style={styles.summaryStats}>
          <View style={styles.summaryStat}>
            <Text style={styles.summaryValue}>{completedCases}</Text>
            <Text style={styles.summaryLabel}>完成病例</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryStat}>
            <Text style={styles.summaryValue}>{avgScore}</Text>
            <Text style={styles.summaryLabel}>平均分</Text>
          </View>
          <View style={styles.summaryDivider} />
          <View style={styles.summaryStat}>
            <Text style={styles.summaryValue}>{totalMinutes}</Text>
            <Text style={styles.summaryLabel}>学习分钟</Text>
          </View>
        </View>
      </View>

      {hasData ? (
        <>
          {data?.subjectScores && data.subjectScores.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <View>
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
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Layout.screenPaddingBottom,
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
  summaryCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    padding: Layout.cardPadding,
    marginBottom: Layout.sectionGap,
  },
  summaryTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  summaryDescription: {
    fontSize: 15,
    lineHeight: 24,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  summaryStats: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  summaryStat: {
    flex: 1,
    alignItems: 'center',
  },
  summaryDivider: {
    width: StyleSheet.hairlineWidth,
    height: 34,
    backgroundColor: Colors.border,
  },
  summaryValue: {
    fontSize: 18,
    lineHeight: 22,
    fontWeight: '800',
    color: Colors.textPrimary,
  },
  summaryLabel: {
    fontSize: 12,
    lineHeight: 16,
    color: Colors.textTertiary,
    marginTop: 3,
  },
  section: {
    marginBottom: Layout.sectionGap,
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
    minHeight: Layout.listRowHeight,
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
    minHeight: Layout.listRowHeightCompact,
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

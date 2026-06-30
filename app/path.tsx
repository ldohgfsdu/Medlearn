import React, { useMemo } from 'react'

export const options = { headerTitle: '学习路径' }
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native'
import { useRouter, useLocalSearchParams } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '@/hooks/useAuth'
import { useLearningPath, useNextRecommended } from '@/hooks/useLearningPath'
import { Colors, Typography, Spacing, BorderRadius, Shadows } from '@/constants/theme'
import type { LearningPathNode } from '@/services/learning-path'
import { resolveTarget } from '@/utils/routeBuilders'

const STATUS_CONFIG: Record<LearningPathNode['status'], { icon: keyof typeof Ionicons.glyphMap; label: string; color: string; bg: string }> = {
  mastered: { icon: 'checkmark-circle', label: '已掌握', color: Colors.success, bg: '#ECFDF5' },
  in_progress: { icon: 'sync-circle', label: '学习中', color: Colors.info, bg: '#EFF6FF' },
  available: { icon: 'lock-open-outline', label: '可学习', color: Colors.warning, bg: '#FFFBEB' },
  locked: { icon: 'lock-closed-outline', label: '锁定', color: Colors.neutral[400], bg: Colors.neutral[100] },
}

export default function LearningPathScreen() {
  const { subject } = useLocalSearchParams<{ subject?: string }>()
  const { user } = useAuth()
  const router = useRouter()

  const { data: path, isLoading } = useLearningPath(user?.id, subject || '')
  const { data: nextNode } = useNextRecommended(user?.id, subject || '')

  // 按章节分组
  const chapterGroups = useMemo(() => {
    if (!path) return []
    const map = new Map<string, LearningPathNode[]>()
    for (const node of path.nodes) {
      const ch = node.chapter || '未分类'
      if (!map.has(ch)) map.set(ch, [])
      map.get(ch)!.push(node)
    }
    return Array.from(map.entries()).map(([chapter, nodes]) => ({ chapter, nodes }))
  }, [path])

  if (!subject) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="map-outline" size={48} color={Colors.neutral[300]} />
        <Text style={styles.emptyTitle}>请从知识地图选择科目</Text>
        <TouchableOpacity style={styles.emptyBtn} onPress={() => router.push('/map')}>
          <Text style={styles.emptyBtnText}>前往知识地图</Text>
        </TouchableOpacity>
      </View>
    )
  }

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary[500]} />
        <Text style={styles.loadingText}>正在生成学习路径...</Text>
      </View>
    )
  }

  if (!path || path.nodes.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Ionicons name="book-outline" size={48} color={Colors.neutral[300]} />
        <Text style={styles.emptyTitle}>暂无学习路径数据</Text>
        <Text style={styles.emptyHint}>该科目可能尚未导入知识点</Text>
        <TouchableOpacity style={styles.emptyBtn} onPress={() => router.replace('/map')}>
          <Text style={styles.emptyBtnText}>重新选择科目</Text>
        </TouchableOpacity>
      </View>
    )
  }

  const masteredCount = path.nodes.filter(n => n.status === 'mastered').length
  const inProgressCount = path.nodes.filter(n => n.status === 'in_progress').length
  const availableCount = path.nodes.filter(n => n.status === 'available').length
  const lockedCount = path.nodes.filter(n => n.status === 'locked').length

  const handleNodePress = (node: LearningPathNode) => {
    if (node.status === 'locked') return
    const target = resolveTarget(node)
    if (target) router.push(target)
  }

  return (
    <View style={styles.container}>
      {/* 顶部：科目名 + 进度条 */}
      <View style={styles.header}>
        <Text style={styles.subjectTitle}>{subject}</Text>
        <Text style={styles.progressLabel}>学习进度</Text>
        <View style={styles.progressBarBg}>
          <View style={[styles.progressBarFill, { width: `${path.progress}%` }]} />
        </View>
        <Text style={styles.progressText}>{path.progress}% 已掌握 ({masteredCount}/{path.nodes.length})</Text>
      </View>

      {/* 统计卡片 */}
      <View style={styles.statsRow}>
        <StatCard icon="checkmark-circle" label="已掌握" value={masteredCount} color={Colors.success} />
        <StatCard icon="sync-circle" label="学习中" value={inProgressCount} color={Colors.info} />
        <StatCard icon="lock-open-outline" label="可学习" value={availableCount} color={Colors.warning} />
        <StatCard icon="lock-closed-outline" label="锁定" value={lockedCount} color={Colors.neutral[400]} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* 按章节分组展示 */}
        {chapterGroups.map(({ chapter, nodes }) => {
          const chapterMastered = nodes.filter(n => n.status === 'mastered').length
          const chapterProgress = nodes.length > 0 ? Math.round((chapterMastered / nodes.length) * 100) : 0

          return (
            <View key={chapter} style={styles.chapterCard}>
              <View style={styles.chapterHeader}>
                <View style={styles.chapterHeaderLeft}>
                  <Ionicons name="book" size={16} color={Colors.primary[500]} />
                  <Text style={styles.chapterTitle} numberOfLines={1}>{chapter}</Text>
                </View>
                <Text style={styles.chapterProgress}>{chapterProgress}%</Text>
              </View>
              <View style={styles.chapterProgressBarBg}>
                <View style={[styles.chapterProgressBarFill, { width: `${chapterProgress}%` }]} />
              </View>
              <View style={styles.chapterBody}>
                {nodes.map(node => {
                  const cfg = STATUS_CONFIG[node.status]
                  const isNext = nextNode?.id === node.id
                  return (
                    <TouchableOpacity
                      key={node.id}
                      style={[styles.nodeItem, isNext && styles.nodeItemHighlight, node.status === 'locked' && styles.nodeItemLocked]}
                      onPress={() => handleNodePress(node)}
                      activeOpacity={node.status === 'locked' ? 1 : 0.7}
                    >
                      <View style={styles.nodeLeft}>
                        <Ionicons name={cfg.icon} size={18} color={cfg.color} />
                        <Text style={[styles.nodeTitle, node.status === 'locked' && styles.nodeTitleLocked]} numberOfLines={1}>
                          {node.title}
                        </Text>
                      </View>
                      <View style={styles.nodeRight}>
                        {node.mastery > 0 && node.status !== 'locked' && (
                          <Text style={[styles.nodeMastery, { color: cfg.color }]}>{node.mastery}%</Text>
                        )}
                        {isNext && <Text style={styles.nextBadge}>推荐</Text>}
                        {node.status !== 'locked' && (
                          <Ionicons name="chevron-forward" size={14} color={Colors.neutral[300]} />
                        )}
                      </View>
                    </TouchableOpacity>
                  )
                })}
              </View>
            </View>
          )
        })}

        {/* 推荐学习卡片 */}
        {nextNode && (
          <View style={styles.recommendCard}>
            <View style={styles.recommendHeader}>
              <Ionicons name="bulb" size={20} color={Colors.warning} />
              <Text style={styles.recommendTitle}>推荐学习</Text>
            </View>
            <TouchableOpacity
              style={styles.recommendNode}
              onPress={() => handleNodePress(nextNode)}
              activeOpacity={0.7}
            >
              <View style={styles.recommendNodeLeft}>
                <View style={styles.recommendIconBg}>
                  <Ionicons name="arrow-forward-circle" size={24} color={Colors.primary[500]} />
                </View>
                <View style={styles.recommendNodeInfo}>
                  <Text style={styles.recommendNodeTitle}>{nextNode.title}</Text>
                  <Text style={styles.recommendNodeMeta}>
                    {nextNode.chapter} · 掌握度 {nextNode.mastery}%
                  </Text>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={20} color={Colors.primary[500]} />
            </TouchableOpacity>
          </View>
        )}

        {/* 全部掌握 */}
        {!nextNode && path.progress === 100 && (
          <View style={styles.completeCard}>
            <Ionicons name="trophy" size={32} color={Colors.warning} />
            <Text style={styles.completeTitle}>恭喜！全部掌握</Text>
            <Text style={styles.completeHint}>{subject}的所有知识点已全部掌握</Text>
          </View>
        )}
      </ScrollView>
    </View>
  )
}

function StatCard({ icon, label, value, color }: { icon: keyof typeof Ionicons.glyphMap; label: string; value: number; color: string }) {
  return (
    <View style={styles.statCard}>
      <Ionicons name={icon} size={18} color={color} />
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
  },
  loadingText: {
    marginTop: Spacing.sm,
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
    paddingHorizontal: Spacing.xl,
  },
  emptyTitle: {
    ...Typography.titleMedium,
    color: Colors.textSecondary,
    marginTop: Spacing.md,
  },
  emptyHint: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
  emptyBtn: {
    marginTop: Spacing.lg,
    backgroundColor: Colors.primary[500],
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.lg,
  },
  emptyBtnText: {
    ...Typography.labelLarge,
    color: '#fff',
  },
  // 头部
  header: {
    backgroundColor: Colors.surface,
    paddingHorizontal: Spacing.base,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  subjectTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  progressLabel: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.md,
    marginBottom: Spacing.xs,
  },
  progressBarBg: {
    height: 8,
    backgroundColor: Colors.neutral[100],
    borderRadius: BorderRadius.full,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: Colors.primary[500],
    borderRadius: BorderRadius.full,
  },
  progressText: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    marginTop: Spacing.xs,
  },
  // 统计行
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.md,
    gap: Spacing.sm,
  },
  statCard: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.xs,
    alignItems: 'center',
    ...Shadows.level1,
  },
  statValue: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
    marginTop: 2,
  },
  statLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  // 滚动内容
  scrollContent: {
    paddingHorizontal: Spacing.base,
    paddingBottom: Spacing['3xl'],
  },
  // 章节卡片
  chapterCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.md,
    overflow: 'hidden',
    ...Shadows.level1,
  },
  chapterHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xs,
  },
  chapterHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    flex: 1,
  },
  chapterTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
    flex: 1,
  },
  chapterProgress: {
    ...Typography.labelMedium,
    color: Colors.primary[500],
  },
  chapterProgressBarBg: {
    height: 3,
    backgroundColor: Colors.neutral[100],
    marginHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    overflow: 'hidden',
  },
  chapterProgressBarFill: {
    height: '100%',
    backgroundColor: Colors.primary[400],
    borderRadius: BorderRadius.full,
  },
  chapterBody: {
    paddingTop: Spacing.xs,
  },
  // 知识点
  nodeItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  nodeItemHighlight: {
    backgroundColor: Colors.primaryLight,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary[500],
  },
  nodeItemLocked: {
    opacity: 0.5,
  },
  nodeLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    flex: 1,
  },
  nodeTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    flex: 1,
  },
  nodeTitleLocked: {
    color: Colors.textTertiary,
  },
  nodeRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  nodeMastery: {
    ...Typography.labelSmall,
    fontWeight: '600',
  },
  nextBadge: {
    ...Typography.labelSmall,
    color: '#fff',
    backgroundColor: Colors.primary[500],
    paddingHorizontal: Spacing.xs,
    paddingVertical: 1,
    borderRadius: BorderRadius.sm,
    overflow: 'hidden',
  },
  // 推荐卡片
  recommendCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
    marginTop: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.primary[200],
    ...Shadows.level2,
  },
  recommendHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  recommendTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  recommendNode: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.md,
  },
  recommendNodeLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    flex: 1,
  },
  recommendIconBg: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.primaryLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recommendNodeInfo: {
    flex: 1,
  },
  recommendNodeTitle: {
    ...Typography.bodyLarge,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  recommendNodeMeta: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  // 全部掌握
  completeCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.xl,
    alignItems: 'center',
    marginTop: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.primary[200],
    ...Shadows.level2,
  },
  completeTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
    marginTop: Spacing.sm,
  },
  completeHint: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
})

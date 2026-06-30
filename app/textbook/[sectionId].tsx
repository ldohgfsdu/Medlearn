import { useState } from 'react'
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, useLocalSearchParams, useRouter } from 'expo-router'
import { useQuery } from '@tanstack/react-query'
import { Colors, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import {
  getRespiratorySectionTitle,
  getSectionDetail,
  type TextbookKnowledgeNode,
} from '@/services/textbookService'

const BADGE_LABELS: Record<string, string> = {
  textbook_grounded: '教材依据',
  page_bound: '页码绑定',
  conservative_fallback: '原文降级',
  merged: '相邻合并',
  grouped: '同类聚合',
  'group:classification': '分类',
  'group:treatment': '治疗',
}

function badgeLabel(value: string): string {
  return BADGE_LABELS[value] ?? value
}

function renderTypeLabel(node: TextbookKnowledgeNode): string {
  if (node.renderType === 'evidence_only') return '教材原文'
  if (node.renderType === 'grouped') return '聚合条目'
  if (node.renderType === 'merged') return '合并知识点'
  return '整理知识点'
}

function KnowledgeNodeItem({ node, isLast }: { node: TextbookKnowledgeNode; isLast: boolean }) {
  const [expanded, setExpanded] = useState(node.renderType === 'evidence_only')
  const evidenceText = expanded ? node.evidenceFull : node.evidenceExcerpt
  const isEvidenceOnly = node.renderType === 'evidence_only'
  const isGrouped = node.renderType === 'grouped'

  return (
    <View style={[
      styles.nodeItem,
      isEvidenceOnly && styles.evidenceOnlyItem,
      isGrouped && styles.groupedItem,
      !isLast && styles.nodeDivider,
    ]}>
      <View style={styles.nodeHeader}>
        <View style={styles.nodeTitleBlock}>
          <Text style={styles.renderLabel}>{renderTypeLabel(node)}</Text>
          <Text style={styles.nodeTitle}>{node.title}</Text>
        </View>
        <View style={styles.pagePill}>
          <Text style={styles.pagePillText}>{node.pageLabel}</Text>
        </View>
      </View>

      {node.sourceHeading ? <Text style={styles.sourceHeading}>{node.sourceHeading}</Text> : null}

      <View style={styles.badgeRow}>
        {node.qualityBadges.map((badge) => (
          <Text
            key={badge}
            style={[
              styles.qualityBadge,
              badge === 'conservative_fallback' && styles.fallbackBadge,
              badge === 'grouped' && styles.groupedBadge,
            ]}
          >
            {badgeLabel(badge)}
          </Text>
        ))}
      </View>

      {node.content ? (
        <Text style={styles.nodeContent}>{node.content}</Text>
      ) : isEvidenceOnly ? (
        <Text style={styles.fallbackCopy}>本条未展示 AI 整理内容，直接呈现教材原文证据。</Text>
      ) : null}

      {node.listItems.length > 0 ? (
        <View style={styles.itemList}>
          {node.listItems.map((item, index) => (
            <View key={`${node.id}-${index}`} style={styles.listItem}>
              <Text style={styles.listIndex}>{index + 1}.</Text>
              <View style={styles.listCopy}>
                <View style={styles.listTitleRow}>
                  <Text style={styles.listTitle}>{item.title}</Text>
                  {item.pageLabel ? <Text style={styles.listPage}>{item.pageLabel}</Text> : null}
                </View>
                <Text style={styles.listBody}>{item.body}</Text>
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {evidenceText ? (
        <TouchableOpacity
          style={[
            styles.evidenceBlock,
            isEvidenceOnly && styles.evidenceOnlyBlock,
            isGrouped && styles.groupedEvidenceBlock,
          ]}
          activeOpacity={0.72}
          onPress={() => setExpanded((value) => !value)}
        >
          <View style={styles.evidenceHeader}>
            <Text style={styles.evidenceLabel}>教材原文证据</Text>
            <Ionicons
              name={expanded ? 'chevron-up' : 'chevron-down'}
              size={16}
              color={Colors.textTertiary}
            />
          </View>
          <Text style={styles.evidenceText}>{evidenceText}</Text>
          {expanded && node.artifactIds.length > 0 ? (
            <Text style={styles.artifactText}>Artifact: {node.artifactIds.join(', ')}</Text>
          ) : null}
          {expanded && node.sourceNodeIds.length > 1 ? (
            <Text style={styles.artifactText}>Source nodes: {node.sourceNodeIds.length}</Text>
          ) : null}
        </TouchableOpacity>
      ) : (
        <Text style={styles.evidenceMissing}>教材证据暂不可用</Text>
      )}
    </View>
  )
}

export default function TextbookSectionScreen() {
  const router = useRouter()
  const { sectionId = '' } = useLocalSearchParams<{ sectionId?: string }>()
  const sectionTitle = getRespiratorySectionTitle(sectionId)
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['textbookSection', sectionId, 'ev1-display-contract'],
    queryFn: () => getSectionDetail(sectionId),
    enabled: !!sectionId,
    staleTime: 300_000,
  })

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Stack.Screen options={{ title: sectionTitle ?? '章节详情' }} />
      <TouchableOpacity style={styles.backRow} onPress={() => router.back()} activeOpacity={0.7}>
        <Ionicons name="chevron-back" size={18} color={Colors.textSecondary} />
        <Text style={styles.backText}>电子教材</Text>
      </TouchableOpacity>

      {isLoading ? (
        <View style={styles.stateBlock}>
          <ActivityIndicator color={Colors.primary[700]} />
          <Text style={styles.stateText}>正在读取章节内容</Text>
        </View>
      ) : null}

      {error ? (
        <View style={styles.stateBlock}>
          <Ionicons name="alert-circle-outline" size={28} color={Colors.error} />
          <Text style={styles.stateTitle}>章节暂时不可用</Text>
          <Text style={styles.stateText}>请稍后重试，或检查本地 display contract fixture。</Text>
          <TouchableOpacity style={styles.retryButton} onPress={() => refetch()} disabled={isFetching}>
            <Text style={styles.retryText}>{isFetching ? '重试中' : '重新读取'}</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {!isLoading && !error && !data ? (
        <View style={styles.stateBlock}>
          <Ionicons name="document-text-outline" size={30} color={Colors.neutral[300]} />
          <Text style={styles.stateTitle}>没有找到这个章节</Text>
          <Text style={styles.stateText}>当前本地预览只开放已导出的 EV1 display contract 章节。</Text>
        </View>
      ) : null}

      {data ? (
        <>
          <View style={styles.headerBlock}>
            <Text style={styles.sourceLine}>{data.textbookTitle} · {data.partTitle}</Text>
            <Text style={styles.title}>{data.section.sectionTitle}</Text>
            <View style={styles.metaGrid}>
              <View style={styles.metaItem}>
                <Text style={styles.metaLabel}>教材层级</Text>
                <Text style={styles.metaValue}>{data.partTitle}</Text>
              </View>
              <View style={styles.metaItem}>
                <Text style={styles.metaLabel}>页码范围</Text>
                <Text style={styles.metaValue}>{data.section.pageRange} 页</Text>
              </View>
              <View style={styles.metaItem}>
                <Text style={styles.metaLabel}>视图节点</Text>
                <Text style={styles.metaValue}>{data.section.nodeCount} 条</Text>
              </View>
            </View>
            <View style={styles.summaryRow}>
              <Text style={styles.summaryBadge}>整理 {data.section.organizedCount}</Text>
              <Text style={styles.summaryBadge}>原文 {data.section.evidenceOnlyCount}</Text>
              <Text style={styles.summaryBadge}>聚合 {data.section.groupedCount}</Text>
              <Text style={styles.summaryBadge}>合并 {data.section.mergedCount}</Text>
            </View>
          </View>

          <View style={styles.sectionHeader}>
            <Text style={styles.sectionHeaderTitle}>知识点</Text>
            <Text style={styles.sectionHeaderMeta}>点击证据展开原文</Text>
          </View>

          <View style={styles.nodeList}>
            {data.nodes.length > 0 ? data.nodes.map((node, index) => (
              <KnowledgeNodeItem key={node.id} node={node} isLast={index === data.nodes.length - 1} />
            )) : (
              <Text style={styles.emptyText}>本章暂时没有可展示的知识点。</Text>
            )}
          </View>
        </>
      ) : null}
    </ScrollView>
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
  backRow: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: Spacing.xs,
    marginTop: Spacing.xs,
  },
  backText: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
  },
  headerBlock: {
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.lg,
  },
  sourceLine: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
  },
  title: {
    fontSize: 22,
    lineHeight: 29,
    fontWeight: '800',
    color: Colors.textPrimary,
    marginTop: Spacing.xs,
  },
  metaGrid: {
    marginTop: Spacing.base,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    overflow: 'hidden',
  },
  metaItem: {
    minHeight: 54,
    paddingHorizontal: Layout.cardPadding,
    paddingVertical: Spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  metaLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  metaValue: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    marginTop: 2,
  },
  summaryRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  summaryBadge: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
    backgroundColor: Colors.primary[50],
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: 12,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  sectionHeaderTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  sectionHeaderMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  nodeList: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    overflow: 'hidden',
  },
  nodeItem: {
    paddingHorizontal: Layout.cardPadding,
    paddingVertical: Spacing.md,
  },
  evidenceOnlyItem: {
    backgroundColor: Colors.neutral[50],
  },
  groupedItem: {
    backgroundColor: Colors.surface,
  },
  nodeDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  nodeHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.sm,
  },
  nodeTitleBlock: {
    flex: 1,
  },
  renderLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginBottom: 2,
  },
  nodeTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  pagePill: {
    minHeight: 24,
    justifyContent: 'center',
    paddingHorizontal: Spacing.sm,
    borderRadius: 12,
    backgroundColor: Colors.primary[50],
  },
  pagePillText: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
  },
  sourceHeading: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
    marginTop: Spacing.sm,
  },
  qualityBadge: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    backgroundColor: Colors.primary[50],
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: 10,
  },
  fallbackBadge: {
    color: Colors.warning,
    backgroundColor: Colors.neutral[100],
  },
  groupedBadge: {
    color: Colors.info,
    backgroundColor: Colors.neutral[100],
  },
  nodeContent: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  fallbackCopy: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.sm,
  },
  itemList: {
    marginTop: Spacing.sm,
    gap: Spacing.sm,
  },
  listItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.sm,
  },
  listIndex: {
    width: 24,
    ...Typography.bodyMedium,
    color: Colors.primary[700],
    fontWeight: '700',
  },
  listCopy: {
    flex: 1,
  },
  listTitleRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: Spacing.sm,
  },
  listTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
    flex: 1,
  },
  listPage: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  listBody: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  evidenceBlock: {
    marginTop: Spacing.sm,
    paddingLeft: Spacing.md,
    borderLeftWidth: 2,
    borderLeftColor: Colors.primary[200],
    minHeight: 44,
  },
  evidenceOnlyBlock: {
    borderLeftColor: Colors.warning,
  },
  groupedEvidenceBlock: {
    borderLeftColor: Colors.info,
  },
  evidenceHeader: {
    minHeight: 28,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  evidenceLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  evidenceText: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
  },
  artifactText: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
  evidenceMissing: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.sm,
    fontStyle: 'italic',
  },
  emptyText: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
    textAlign: 'center',
    padding: Spacing.xl,
  },
  stateBlock: {
    minHeight: 180,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    padding: Spacing.xl,
    marginTop: Spacing.md,
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
  retryButton: {
    minHeight: 44,
    paddingHorizontal: Spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 22,
    backgroundColor: Colors.primary[700],
    marginTop: Spacing.md,
  },
  retryText: {
    ...Typography.labelLarge,
    color: Colors.surface,
    fontWeight: '700',
  },
})

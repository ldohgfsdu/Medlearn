import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { ActivityIndicator, LayoutAnimation, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, type Href, useLocalSearchParams, useRouter } from 'expo-router'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useQuery } from '@tanstack/react-query'
import { BorderRadius, Colors, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { getSectionDetail } from '@/services/textbookService'
import {
  isPhase1VisualEvidenceSection,
  locatorIdsForEvidenceArtifact,
} from '@/services/phase1VisualEvidenceService'
import {
  findChapterStudyUnit,
  type StudyEvidence,
  type StudyGroup,
  type StudyGroupItem,
  type StudyUnit,
} from '@/utils/textbookStudy'

function compactText(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function EvidenceToggle({
  body,
  defaultExpanded = false,
  evidence,
  evidenceOnly = false,
  pageLabel,
  sectionId,
}: {
  body: string
  defaultExpanded?: boolean
  evidence: StudyEvidence[]
  evidenceOnly?: boolean
  pageLabel: string
  sectionId: string
}) {
  const router = useRouter()
  const [expanded, setExpanded] = useState(defaultExpanded)
  const availableEvidence = evidence.filter((item) => item.text)
  if (availableEvidence.length === 0) {
    if (!compactText(body)) {
      return (
        <Text style={styles.emptyHint}>
          {evidenceOnly ? '暂无原文' : '暂无整理结论'}
        </Text>
      )
    }
    return null
  }
  const evidenceText = availableEvidence.map((item) => item.text).join('\n\n')
  if (compactText(body) === compactText(evidenceText)) return null

  const toggleExpanded = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut)
    setExpanded((value) => !value)
  }

  return (
    <View style={styles.evidenceBlock}>
      <TouchableOpacity style={styles.evidenceTrigger} activeOpacity={0.72} onPress={toggleExpanded}>
        <Text style={styles.evidenceTriggerText}>
          原文 {pageLabel || availableEvidence[0].pageLabel} · {expanded ? '收起' : '展开'}
        </Text>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={13} color={Colors.textTertiary} />
      </TouchableOpacity>
      {expanded ? (
        <View style={styles.evidenceTextBlock}>
          {availableEvidence.map((item) => {
            const locatorIds = locatorIdsForEvidenceArtifact(
              sectionId,
              item.id,
              item.sourceLocatorIds,
            )
            const showPageViewer =
              isPhase1VisualEvidenceSection(sectionId) && locatorIds.length > 0
            const label = item.pageLabel.replace(/^p\.?/i, '') || pageLabel
            return (
              <View key={item.id} style={styles.evidenceEntry}>
                <Text style={styles.evidenceText}>
                  <Text style={styles.evidencePage}>({item.pageLabel}) </Text>
                  {item.text}
                </Text>
                {showPageViewer ? (
                  <TouchableOpacity
                    style={styles.textbookPageButton}
                    activeOpacity={0.75}
                    onPress={() => {
                      router.push({
                        pathname: '/textbook/page-viewer',
                        params: {
                          sectionId,
                          locatorIds: locatorIds.join(','),
                          pageLabel: label.replace(/^P/i, ''),
                        },
                      } as unknown as Href)
                    }}
                  >
                    <Ionicons name="book-outline" size={14} color={Colors.primary[700]} />
                    <Text style={styles.textbookPageButtonText}>
                      教材原文 P{label.replace(/^P/i, '')}
                    </Text>
                  </TouchableOpacity>
                ) : null}
              </View>
            )
          })}
        </View>
      ) : null}
    </View>
  )
}

function StudyItemRow({
  compact,
  highlightedItemId,
  index,
  item,
  sectionId,
  targetItemRef,
  targetItemId,
}: {
  compact: boolean
  highlightedItemId?: string
  index: number
  item: StudyGroupItem
  sectionId: string
  targetItemRef?: RefObject<View | null>
  targetItemId?: string
}) {
  const body = item.body.trim()
  const showTitle = item.title.trim() && item.title.trim() !== body
  const children = item.children ?? []
  const isTarget = targetItemId === item.id
  const isHighlighted = highlightedItemId === item.id

  return (
    <View
      style={[styles.studyItem, isHighlighted && styles.targetedStudyItem]}
      ref={isTarget ? targetItemRef : undefined}
    >
      {compact ? (
        <Text style={styles.studyIndex}>{index + 1}.</Text>
      ) : null}
      <View style={styles.studyItemCopy}>
        {showTitle ? (
          <View style={styles.itemTitleRow}>
            <Text style={styles.itemTitle}>{item.title}</Text>
            {item.pageLabel ? (
              <Text style={styles.itemPage} numberOfLines={1}>
                {item.pageLabel}
              </Text>
            ) : null}
          </View>
        ) : null}
        {item.evidenceOnly && body ? (
          <View style={styles.originalBadge}>
            <Text style={styles.originalBadgeText}>原文</Text>
          </View>
        ) : null}
        {body ? (
          <Text style={item.evidenceOnly ? styles.originalBody : styles.itemBody}>
            {body}
          </Text>
        ) : null}
        <EvidenceToggle
          body={body}
          defaultExpanded={isTarget}
          evidence={item.evidence}
          evidenceOnly={item.evidenceOnly}
          pageLabel={item.pageLabel}
          sectionId={sectionId}
        />
        <StudyChildList
          highlightedItemId={highlightedItemId}
          items={children}
          level={0}
          sectionId={sectionId}
          targetItemRef={targetItemRef}
          targetItemId={targetItemId}
        />
      </View>
    </View>
  )
}

const CHILD_BORDER_COLORS = [
  Colors.border,
  Colors.primary[100],
  Colors.primary[200],
  Colors.primary[300],
  Colors.primary[400],
]

function StudyChildList({
  highlightedItemId,
  items,
  level,
  sectionId,
  targetItemRef,
  targetItemId,
}: {
  highlightedItemId?: string
  items: StudyGroupItem[]
  level: number
  sectionId: string
  targetItemRef?: RefObject<View | null>
  targetItemId?: string
}) {
  if (items.length === 0) return null

  const cappedLevel = Math.min(level, 4)
  const levelPadding = Spacing.sm + cappedLevel * Spacing.xs
  const borderColour = CHILD_BORDER_COLORS[cappedLevel]

  return (
    <View
      style={[
        styles.childList,
        {
          paddingLeft: levelPadding,
          borderLeftColor: borderColour,
        },
      ]}
    >
      {items.map((child, childIndex) => {
        const isTarget = targetItemId === child.id
        const isHighlighted = highlightedItemId === child.id
        return (
          <View
            key={child.id}
            style={[styles.childItem, isHighlighted && styles.targetedStudyItem]}
            ref={isTarget ? targetItemRef : undefined}
          >
            <Text style={styles.childIndex}>{childIndex + 1}.</Text>
            <View style={styles.childCopy}>
              <View style={styles.itemTitleRow}>
                <Text style={level > 0 ? styles.grandChildTitle : styles.childTitle}>{child.title}</Text>
                {child.pageLabel ? (
                  <Text style={styles.itemPage} numberOfLines={1}>
                    {child.pageLabel}
                  </Text>
                ) : null}
              </View>
              {child.evidenceOnly && child.body ? (
                <View style={styles.originalBadge}>
                  <Text style={styles.originalBadgeText}>原文</Text>
                </View>
              ) : null}
              {child.body ? (
                <Text style={child.evidenceOnly ? styles.originalBody : styles.itemBody}>
                  {child.body}
                </Text>
              ) : null}
              <EvidenceToggle
                body={child.body}
                defaultExpanded={isTarget}
                evidence={child.evidence}
                evidenceOnly={child.evidenceOnly}
                pageLabel={child.pageLabel}
                sectionId={sectionId}
              />
              <StudyChildList
                highlightedItemId={highlightedItemId}
                items={child.children ?? []}
                level={level + 1}
                sectionId={sectionId}
                targetItemRef={targetItemRef}
                targetItemId={targetItemId}
              />
            </View>
          </View>
        )
      })}
    </View>
  )
}

const DEFAULT_VISIBLE_ITEMS = 10

function StudyGroupBlock({
  containsTarget,
  expanded,
  group,
  highlightedItemId,
  isLast,
  onToggle,
  sectionId,
  targetItemRef,
  targetItemId,
}: {
  containsTarget: boolean
  expanded: boolean
  group: StudyGroup
  highlightedItemId?: string
  isLast: boolean
  onToggle: () => void
  sectionId: string
  targetItemRef?: RefObject<View | null>
  targetItemId?: string
}) {
  const compact = group.items.length > 1
  const [showAll, setShowAll] = useState(containsTarget)
  useEffect(() => {
    if (containsTarget) setShowAll(true)
  }, [containsTarget])

  const visibleItems = showAll ? group.items : group.items.slice(0, DEFAULT_VISIBLE_ITEMS)
  const hiddenCount = group.items.length - visibleItems.length

  return (
    <View style={[styles.groupBlock, !isLast && styles.groupDivider]}>
      <TouchableOpacity
        style={styles.groupHeader}
        activeOpacity={0.72}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        onPress={onToggle}
      >
        <View style={styles.groupHeaderCopy}>
          <Text style={styles.groupTitle}>{group.title}</Text>
          <Text style={styles.groupMeta}>
            {group.items.length} 条{group.pageLabel ? ` · ${group.pageLabel}` : ''}
          </Text>
        </View>
        <Ionicons
          name={expanded ? 'chevron-up' : 'chevron-down'}
          size={18}
          color={Colors.textTertiary}
        />
      </TouchableOpacity>
      {expanded ? (
        <View style={compact ? styles.numberedList : styles.singleItem}>
          {visibleItems.map((item, index) => (
            <StudyItemRow
              key={item.id}
              compact={compact}
              highlightedItemId={highlightedItemId}
              index={index}
              item={item}
              sectionId={sectionId}
              targetItemRef={targetItemRef}
              targetItemId={targetItemId}
            />
          ))}
          {hiddenCount > 0 ? (
            <TouchableOpacity
              style={styles.showMoreButton}
              activeOpacity={0.72}
              onPress={() => setShowAll(true)}
            >
              <Text style={styles.showMoreText}>
                显示更多（剩余 {hiddenCount} 条）
              </Text>
              <Ionicons name="chevron-down" size={14} color={Colors.textTertiary} />
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}
    </View>
  )
}

function findStudyItem(items: StudyGroupItem[], itemId: string): StudyGroupItem | null {
  for (const item of items) {
    if (item.id === itemId) return item
    const child = findStudyItem(item.children ?? [], itemId)
    if (child) return child
  }
  return null
}

function findTargetItem(unit: StudyUnit | null, itemId: string): StudyGroupItem | null {
  if (!unit || !itemId) return null
  for (const group of unit.groups) {
    const item = findStudyItem(group.items, itemId)
    if (item) return item
  }
  return null
}

function groupContainsTarget(group: StudyGroup, itemId: string): boolean {
  return Boolean(itemId) && Boolean(findStudyItem(group.items, itemId))
}

function TargetEvidenceCard({ item }: { item: StudyGroupItem }) {
  const evidence = item.evidence.filter((entry) => entry.text)
  const firstEvidence = evidence[0]
  return (
    <View style={styles.targetCard} testID="wrong-question-target-card">
      <View style={styles.targetHeader}>
        <Ionicons name="locate-outline" size={17} color={Colors.primary[700]} />
        <Text style={styles.targetLabel}>错题定位目标</Text>
      </View>
      <Text style={styles.targetTitle} testID="wrong-question-target-title">{item.title}</Text>
      {item.pageLabel ? <Text style={styles.targetPage} testID="wrong-question-target-page">{item.pageLabel}</Text> : null}
      {firstEvidence ? (
        <View style={styles.targetEvidenceBox}>
          <Text style={styles.targetEvidenceLabel}>教材原文证据</Text>
          <Text style={styles.targetEvidenceText} testID="wrong-question-target-evidence">
            <Text style={styles.evidencePage}>({firstEvidence.pageLabel || item.pageLabel}) </Text>
            {firstEvidence.text}
          </Text>
        </View>
      ) : null}
    </View>
  )
}

export default function TextbookUnitScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { sectionId = '', targetItemId = '', unitId = '', from = '' } = useLocalSearchParams<{
    sectionId?: string
    targetItemId?: string
    unitId?: string
    from?: string
  }>()
  const fromWrongQuestion = from === 'wrong-question'
  const fromKnowledgeMap = from === 'map'
  const hasTargetItem = Boolean(targetItemId)
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})
  const [highlightedItemId, setHighlightedItemId] = useState<string | undefined>(undefined)
  const scrollRef = useRef<ScrollView>(null)
  const targetItemRef = useRef<View>(null)
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['textbookSection', sectionId, 'study-unit', unitId],
    queryFn: () => getSectionDetail(sectionId),
    enabled: !!sectionId && !!unitId,
    staleTime: 300_000,
  })

  const unit = useMemo(() => data ? findChapterStudyUnit(data, unitId) : null, [data, unitId])
  const targetItem = useMemo(
    () => findTargetItem(unit, targetItemId),
    [targetItemId, unit],
  )
  const targetGroupIds = useMemo(() => new Set(
    unit?.groups
      .filter((group) => groupContainsTarget(group, targetItemId))
      .map((group) => group.id) ?? [],
  ), [targetItemId, unit])

  // G4: clear the target highlight shortly after landing
  useEffect(() => {
    if (!targetItemId) {
      setHighlightedItemId(undefined)
      return
    }
    setHighlightedItemId(targetItemId)
    const timer = setTimeout(() => setHighlightedItemId(undefined), 2500)
    return () => clearTimeout(timer)
  }, [targetItemId])

  // G3: scroll the target item into view after layout settles
  useEffect(() => {
    if (!hasTargetItem || !targetItem) return
    const timer = setTimeout(() => {
      const targetView = targetItemRef.current as unknown as null | {
        measureLayout: (
          relativeTo: ScrollView,
          onSuccess: (x: number, y: number, width: number, height: number) => void,
          onFail: () => void,
        ) => void
      }
      const scrollView = scrollRef.current
      if (!targetView || !scrollView || typeof targetView.measureLayout !== 'function') return
      targetView.measureLayout(
        scrollView,
        (_x, y) => {
          scrollView.scrollTo({ y: Math.max(0, y - Spacing.lg), animated: false })
        },
        () => {},
      )
    }, 200)
    return () => clearTimeout(timer)
  }, [hasTargetItem, targetItem])

  // G6: first group expanded by default so the screen reads like a textbook
  const firstGroupId = unit?.groups[0]?.id
  const isGroupExpanded = (groupId: string) => {
    if (expandedGroups[groupId] !== undefined) return expandedGroups[groupId]
    if (targetGroupIds.has(groupId)) return true
    if (groupId === firstGroupId) return true
    return false
  }

  const allExpanded = unit ? unit.groups.every((group) => isGroupExpanded(group.id)) : false

  const toggleAll = () => {
    if (!unit || unit.groups.length === 0) return
    const targetState = !allExpanded
    setExpandedGroups(() => {
      const next: Record<string, boolean> = {}
      for (const group of unit.groups) {
        next[group.id] = targetState
      }
      return next
    })
  }

  const toggleGroup = (groupId: string) => {
    setExpandedGroups((current) => ({
      ...current,
      [groupId]: !isGroupExpanded(groupId),
    }))
  }

  const clearHighlightOnDrag = () => {
    if (highlightedItemId) setHighlightedItemId(undefined)
  }

  const returnToChapter = () => {
    router.replace({
      pathname: '/textbook/[sectionId]',
      params: { sectionId },
    } as unknown as Href)
  }

  return (
    <ScrollView
      ref={scrollRef}
      style={styles.screen}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      onScrollBeginDrag={clearHighlightOnDrag}
    >
      <Stack.Screen options={{ headerShown: false }} />
      <View style={[styles.topBar, { paddingTop: insets.top + Spacing.xs }]}>
        <TouchableOpacity style={styles.iconButton} onPress={returnToChapter} activeOpacity={0.7}>
          <Ionicons name="arrow-back" size={25} color={Colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.topCopy}>
          <Text style={styles.topTitle} numberOfLines={1}>
            {unit?.title ?? '小节详情'}
          </Text>
          {data && unit ? (
            <Text style={styles.topMeta} numberOfLines={1}>
              {data.section.sectionTitle} · {unit.pageLabel || `p.${data.section.pageRange}`}
            </Text>
          ) : null}
        </View>
      </View>

      {isLoading ? (
        <View style={styles.stateBlock}>
          <ActivityIndicator color={Colors.primary[700]} />
          <Text style={styles.stateText}>正在读取小节内容</Text>
        </View>
      ) : null}

      {error ? (
        <View style={styles.stateBlock}>
          <Ionicons name="alert-circle-outline" size={28} color={Colors.error} />
          <Text style={styles.stateTitle}>小节暂时不可用</Text>
          <Text style={styles.stateText}>请稍后重试，或返回章节目录。</Text>
          <TouchableOpacity style={styles.retryButton} onPress={() => refetch()} disabled={isFetching}>
            <Text style={styles.retryText}>{isFetching ? '重试中' : '重新读取'}</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {!isLoading && !error && data && !unit ? (
        <View style={styles.stateBlock}>
          <Ionicons name="document-text-outline" size={30} color={Colors.neutral[300]} />
          <Text style={styles.stateTitle}>没有找到这个小节</Text>
          <Text style={styles.stateText}>这个小节索引可能已经变化，请返回章节目录重新打开。</Text>
        </View>
      ) : null}

      {data && unit ? (
        <>
          <View style={styles.unitIntro}>
            {fromWrongQuestion ? (
              <View style={styles.sourceBadge}>
                <Ionicons name="locate-outline" size={15} color={Colors.primary[700]} />
                <Text style={styles.sourceBadgeText}>来自错题定位，以下为教材原文学习位置</Text>
              </View>
            ) : null}
            {fromKnowledgeMap ? (
              <View style={styles.sourceBadge}>
                <Ionicons name="map-outline" size={15} color={Colors.primary[700]} />
                <Text style={styles.sourceBadgeText}>来自知识地图，已定位到选中的小节</Text>
              </View>
            ) : null}
            <Text style={styles.introLabel}>教材小节</Text>
            <Text style={styles.introTitle}>{unit.title}</Text>
            <Text style={styles.introMeta}>
              {data.partTitle} · {unit.pageLabel || `p.${data.section.pageRange}`} · {unit.itemCount} 条
            </Text>
            {hasTargetItem && targetItem ? <TargetEvidenceCard item={targetItem} /> : null}
          </View>

          <View style={styles.groupList}>
            {unit.groups.length > 1 ? (
              <View style={styles.groupListToolbar}>
                <TouchableOpacity style={styles.expandAllButton} onPress={toggleAll} activeOpacity={0.72}>
                  <Ionicons
                    name={allExpanded ? 'chevron-up-circle-outline' : 'chevron-down-circle-outline'}
                    size={16}
                    color={Colors.textSecondary}
                  />
                  <Text style={styles.expandAllText}>{allExpanded ? '全部收起' : '全部展开'}</Text>
                </TouchableOpacity>
              </View>
            ) : null}
            {unit.groups.map((group, index) => (
              <StudyGroupBlock
                key={group.id}
                containsTarget={hasTargetItem && targetGroupIds.has(group.id)}
                expanded={isGroupExpanded(group.id)}
                group={group}
                highlightedItemId={highlightedItemId}
                isLast={index === unit.groups.length - 1}
                onToggle={() => toggleGroup(group.id)}
                sectionId={sectionId}
                targetItemRef={targetItemRef}
                targetItemId={hasTargetItem ? targetItemId : undefined}
              />
            ))}
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
    paddingBottom: Layout.screenPaddingBottom,
  },
  topBar: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Spacing.xs,
    backgroundColor: Colors.background,
  },
  iconButton: {
    width: 44,
    minHeight: 44,
    alignItems: 'flex-start',
    justifyContent: 'center',
  },
  topCopy: {
    flex: 1,
  },
  topTitle: {
    fontSize: 21,
    lineHeight: 27,
    color: Colors.textPrimary,
    fontWeight: '800',
  },
  topMeta: {
    ...Typography.labelMedium,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  unitIntro: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.base,
  },
  sourceBadge: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: 999,
    backgroundColor: Colors.primaryLight,
    marginBottom: Spacing.sm,
  },
  sourceBadgeText: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '700',
  },
  targetCard: {
    gap: Spacing.sm,
    padding: Spacing.md,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.primary[100],
    backgroundColor: Colors.primary[50],
    marginTop: Spacing.md,
  },
  targetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  targetLabel: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '800',
  },
  targetTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  targetPage: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  targetEvidenceBox: {
    gap: Spacing.xs,
    paddingTop: Spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.primary[100],
  },
  targetEvidenceLabel: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '800',
  },
  targetEvidenceText: {
    fontSize: 15,
    lineHeight: 25,
    color: Colors.textPrimary,
  },
  introLabel: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '800',
  },
  introTitle: {
    fontSize: 26,
    lineHeight: 34,
    color: Colors.textPrimary,
    fontWeight: '800',
    marginTop: Spacing.xs,
  },
  introMeta: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
  groupList: {
    paddingHorizontal: Layout.screenPaddingX,
    backgroundColor: Colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
  },
  groupListToolbar: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xs,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  expandAllButton: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.sm,
  },
  expandAllText: {
    fontSize: 15,
    lineHeight: 20,
    color: Colors.textSecondary,
    fontWeight: '600',
  },
  groupBlock: {
    paddingVertical: Spacing.lg,
  },
  groupDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  groupHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    minHeight: 52,
  },
  groupHeaderCopy: {
    flex: 1,
    minWidth: 0,
  },
  groupTitle: {
    flex: 1,
    fontSize: 18,
    lineHeight: 25,
    color: Colors.textPrimary,
    fontWeight: '800',
  },
  groupMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  groupPage: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  numberedList: {
    gap: Spacing.md,
    marginTop: Spacing.md,
  },
  singleItem: {
    gap: Spacing.sm,
    marginTop: Spacing.md,
  },
  showMoreButton: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: Spacing.xs,
    paddingTop: Spacing.sm,
  },
  showMoreText: {
    fontSize: 15,
    lineHeight: 20,
    color: Colors.textTertiary,
    fontWeight: '500',
  },
  childList: {
    gap: Spacing.sm,
    marginTop: Spacing.sm,
    paddingLeft: Spacing.md,
    borderLeftWidth: 2,
    borderLeftColor: Colors.border,
  },
  childItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.sm,
  },
  childIndex: {
    width: 22,
    fontSize: 15,
    lineHeight: 25,
    color: Colors.textTertiary,
    fontWeight: '700',
  },
  childCopy: {
    flex: 1,
  },
  childTitle: {
    flex: 1,
    fontSize: 16,
    lineHeight: 25,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  grandChildTitle: {
    flex: 1,
    fontSize: 15,
    lineHeight: 24,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  studyItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.sm,
  },
  targetedStudyItem: {
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.primary[50],
    padding: Spacing.sm,
  },
  studyIndex: {
    width: 28,
    fontSize: 17,
    lineHeight: 28,
    color: Colors.primary[700],
    fontWeight: '800',
  },
  studyItemCopy: {
    flex: 1,
  },
  itemTitleRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: Spacing.sm,
  },
  itemTitle: {
    flex: 1,
    fontSize: 17,
    lineHeight: 26,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  itemPage: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    minWidth: 54,
    flexShrink: 0,
    textAlign: 'right',
  },
  itemBody: {
    fontSize: 16,
    lineHeight: 27,
    color: Colors.textPrimary,
  },
  originalBody: {
    fontSize: 16,
    lineHeight: 27,
    color: Colors.textSecondary,
    fontStyle: 'italic',
  },
  originalBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.xs,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
    backgroundColor: Colors.surfaceVariant,
    marginBottom: Spacing.xs,
  },
  originalBadgeText: {
    fontSize: 11,
    lineHeight: 14,
    color: Colors.textTertiary,
    fontWeight: '600',
  },
  emptyHint: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textSecondary,
    fontStyle: 'italic',
    marginTop: Spacing.xs,
  },
  evidenceBlock: {
    marginTop: Spacing.xs,
  },
  evidenceTrigger: {
    minHeight: 44,
    paddingVertical: Spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: Spacing.xs,
  },
  evidenceTriggerText: {
    fontSize: 15,
    lineHeight: 20,
    color: Colors.textTertiary,
  },
  evidenceTextBlock: {
    gap: Spacing.sm,
    paddingTop: Spacing.xs,
  },
  evidenceEntry: {
    gap: Spacing.xs,
  },
  textbookPageButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    paddingVertical: 4,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.sm,
    backgroundColor: Colors.primaryLight,
  },
  textbookPageButtonText: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '700',
  },
  evidenceText: {
    fontSize: 15,
    lineHeight: 25,
    color: Colors.textSecondary,
  },
  evidencePage: {
    color: Colors.error,
    fontWeight: '800',
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
    margin: Layout.screenPaddingX,
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

import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { ActivityIndicator, LayoutAnimation, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, type Href, useLocalSearchParams, useRouter } from 'expo-router'
import { TextbookEditorial, TextbookEditorialFonts } from '@/constants/textbookEditorial'
import {
  buildKnowledgeMapRoute,
  buildTextbookSectionRoute,
  isAllowedMapUnitEntry,
} from '@/utils/routeBuilders'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useQuery } from '@tanstack/react-query'
import { BorderRadius, Colors, FontFamily, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import {
  formatTextbookPageReference,
  getSectionDetail,
} from '@/services/textbookService'

import {
  findChapterStudyUnit,
  isTruncatedText,
  type StudyEvidence,
  type StudyGroup,
  type StudyGroupItem,
  type StudyUnit,
} from '@/utils/textbookStudy'
import {
  bodyMatchesStudyEvidence,
  dedupeCompactEvidenceSourceEntries,
  resolveCompactEvidenceSourceEntry,
  resolveCompactEvidenceSourceEntries,
  resolveStudyEvidencePageReference,
} from '@/utils/studyEvidencePageReference'

function compactText(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function matchingDisplayTitle(left: string, right: string): boolean {
  const normalize = (value: string) => compactText(value)
    .replace(/^第[一二三四五六七八九十百零〇\d]+节\s*[|｜　]?\s*/u, '')
    .replace(/[|｜　\s]/g, '')
  return Boolean(normalize(left)) && normalize(left) === normalize(right)
}

const EVIDENCE_TEXT_PREVIEW_LIMIT = 80
const BODY_PREVIEW_LIMIT = 120

/**
 * Collapsible body text with truncation awareness.
 *
 * - Long body (> BODY_PREVIEW_LIMIT) collapses to a preview by default;
 *   learner taps "展开全文" to read the full organized conclusion.
 * - Truncated body (detected via isTruncatedText) shows a "原文片段" badge
 *   so the learner knows the text is incomplete and should consult the
 *   PageViewer page image for the authoritative complete original.
 * - evidenceOnly body (raw evidence without organized conclusion) keeps the
 *   existing "原文" badge when not truncated.
 */
function CollapsibleBody({
  body,
  evidenceOnly,
}: {
  body: string
  evidenceOnly: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const trimmed = body.trim()
  if (!trimmed) return null

  const isTruncated = isTruncatedText(trimmed)
  const isLong = trimmed.length > BODY_PREVIEW_LIMIT
  const showPreview = !expanded && isLong
  const displayText = showPreview
    ? `${trimmed.slice(0, BODY_PREVIEW_LIMIT).trim()}…`
    : trimmed

  return (
    <View>
      {isTruncated ? (
        <View style={styles.fragmentBadge}>
          <Ionicons name="alert-circle-outline" size={11} color={Colors.warning} />
          <Text style={styles.fragmentBadgeText}>原文片段</Text>
        </View>
      ) : evidenceOnly ? (
        <View style={styles.originalBadge}>
          <Text style={styles.originalBadgeText}>原文</Text>
        </View>
      ) : null}
      <Text style={evidenceOnly ? styles.originalBody : styles.itemBody}>
        {displayText}
      </Text>
      {isLong ? (
        <TouchableOpacity
          style={styles.bodyExpandButton}
          activeOpacity={0.72}
          onPress={() => {
            LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut)
            setExpanded((value) => !value)
          }}
        >
          <Text style={styles.bodyExpandText}>
            {expanded ? '收起' : '展开全文'}
          </Text>
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={12}
            color={Colors.textTertiary}
          />
        </TouchableOpacity>
      ) : null}
    </View>
  )
}

function PageViewerButton({
  locatorIds,
  sectionId,
  viewerActionLabel,
  viewerPageLabel,
}: {
  locatorIds: string[]
  sectionId: string
  viewerActionLabel: string
  viewerPageLabel: string
}) {
  const router = useRouter()
  return (
    <TouchableOpacity
      style={styles.textbookPageButton}
      activeOpacity={0.75}
      onPress={() => {
        router.push({
          pathname: '/textbook/page-viewer',
          params: {
            sectionId,
            locatorIds: locatorIds.join(','),
            pageLabel: viewerPageLabel.replace(/^P/i, ''),
          },
        } as unknown as Href)
      }}
    >
      <Ionicons name="book-outline" size={14} color={Colors.primary[700]} />
      <Text style={styles.textbookPageButtonText}>
        {viewerActionLabel}
      </Text>
    </TouchableOpacity>
  )
}

function CompactEvidenceSource({
  entry,
  sectionId,
}: {
  entry: NonNullable<ReturnType<typeof resolveCompactEvidenceSourceEntry>>
  sectionId: string
}) {
  if (entry.kind === 'page_viewer' && entry.viewerActionLabel) {
    return (
      <PageViewerButton
        locatorIds={entry.locatorIds}
        sectionId={sectionId}
        viewerActionLabel={entry.viewerActionLabel}
        viewerPageLabel={entry.viewerPageLabel}
      />
    )
  }
  return (
    <View style={styles.compactPageReference}>
      <Ionicons name="document-text-outline" size={14} color={Colors.textTertiary} />
      <Text style={styles.compactPageReferenceText}>{entry.pageReference}</Text>
    </View>
  )
}

function EvidenceEntry({
  compact = false,
  item,
  pageLabel,
  sectionId,
}: {
  compact?: boolean
  item: StudyEvidence
  pageLabel: string
  sectionId: string
}) {
  const [textExpanded, setTextExpanded] = useState(false)
  const {
    locatorIds,
    showPageViewer,
    pageReference,
    viewerPageLabel,
    viewerActionLabel,
  } = resolveStudyEvidencePageReference(sectionId, item, pageLabel)

  if (compact) {
    const entry = resolveCompactEvidenceSourceEntry(sectionId, item, pageLabel)
    if (!entry) return null
    return <CompactEvidenceSource entry={entry} sectionId={sectionId} />
  }

  const fullText = item.text
  const isLong = fullText.length > EVIDENCE_TEXT_PREVIEW_LIMIT
  const displayText = textExpanded || !isLong
    ? fullText
    : fullText.slice(0, EVIDENCE_TEXT_PREVIEW_LIMIT).trim()

  return (
    <View style={styles.evidenceEntry}>
      <Text style={styles.evidenceText}>
        <Text style={styles.evidencePage}>（{pageReference}）</Text>
        {displayText}
        {isLong && !textExpanded ? '...' : null}
      </Text>
      {isLong ? (
        <TouchableOpacity
          style={styles.evidenceExpandButton}
          activeOpacity={0.72}
          onPress={() => setTextExpanded((v) => !v)}
        >
          <Text style={styles.evidenceExpandText}>
            {textExpanded ? '收起' : '展开全文'}
          </Text>
          <Ionicons
            name={textExpanded ? 'chevron-up' : 'chevron-down'}
            size={12}
            color={Colors.textTertiary}
          />
        </TouchableOpacity>
      ) : null}
      {showPageViewer && viewerActionLabel ? (
        <PageViewerButton
          locatorIds={locatorIds}
          sectionId={sectionId}
          viewerActionLabel={viewerActionLabel}
          viewerPageLabel={viewerPageLabel}
        />
      ) : null}
    </View>
  )
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
  const bodyMatchesEvidence = bodyMatchesStudyEvidence(body, availableEvidence)
  const firstReferenceKind = availableEvidence[0].pageReferenceKind
  const referenceKind = availableEvidence.every(
    (item) => item.pageReferenceKind === firstReferenceKind,
  )
    ? firstReferenceKind
    : 'pdf'

  if (bodyMatchesEvidence) {
    const compactEntries = dedupeCompactEvidenceSourceEntries(
      resolveCompactEvidenceSourceEntries(
        sectionId,
        availableEvidence,
        pageLabel,
      ),
    )
    if (compactEntries.length === 0) return null
    return (
      <View style={styles.evidenceBlock}>
        <View style={styles.evidenceCollapsedHint}>
          {compactEntries.map((entry, index) => (
            <CompactEvidenceSource
              key={`${entry.viewerPageLabel}-${index}`}
              entry={entry}
              sectionId={sectionId}
            />
          ))}
        </View>
      </View>
    )
  }

  const toggleExpanded = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut)
    setExpanded((value) => !value)
  }

  return (
    <View style={styles.evidenceBlock}>
      <TouchableOpacity style={styles.evidenceTrigger} activeOpacity={0.72} onPress={toggleExpanded}>
        <Text style={styles.evidenceTriggerText}>
          {formatTextbookPageReference(
            pageLabel || availableEvidence[0].pageLabel,
            referenceKind,
          )} · {expanded ? '收起' : '展开'}
        </Text>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={13} color={Colors.textTertiary} />
      </TouchableOpacity>
      {expanded ? (
        <View style={styles.evidenceTextBlock}>
          {availableEvidence.map((item) => (
            <EvidenceEntry
              key={item.id}
              item={item}
              pageLabel={pageLabel}
              sectionId={sectionId}
            />
          ))}
        </View>
      ) : null}
    </View>
  )
}

function shouldShowStudyTitle(
  title: string,
  body: string,
  ...ancestors: string[]
): boolean {
  const trimmed = title.trim()
  if (!trimmed || trimmed === body.trim()) return false
  return !ancestors.some((ancestor) => matchingDisplayTitle(trimmed, ancestor))
}

function StudyItemRow({
  compact,
  groupTitle,
  highlightedItemId,
  index,
  item,
  sectionId,
  targetItemRef,
  targetItemId,
  unitTitle,
}: {
  compact: boolean
  groupTitle: string
  highlightedItemId?: string
  index: number
  item: StudyGroupItem
  sectionId: string
  targetItemRef?: RefObject<View | null>
  targetItemId?: string
  unitTitle: string
}) {
  const body = item.body.trim()
  const showTitle = shouldShowStudyTitle(item.title, body, unitTitle, groupTitle)
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
                {formatTextbookPageReference(item.pageLabel, 'pdf')}
              </Text>
            ) : null}
          </View>
        ) : null}
        <CollapsibleBody body={body} evidenceOnly={item.evidenceOnly} />
        <EvidenceToggle
          body={body}
          defaultExpanded={isTarget || isTruncatedText(body)}
          evidence={item.evidence}
          evidenceOnly={item.evidenceOnly}
          pageLabel={item.pageLabel}
          sectionId={sectionId}
        />
        <StudyChildList
          ancestorTitles={[unitTitle, groupTitle, item.title]}
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
  ancestorTitles,
  highlightedItemId,
  items,
  level,
  sectionId,
  targetItemRef,
  targetItemId,
}: {
  ancestorTitles: string[]
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
        const showChildTitle = shouldShowStudyTitle(child.title, child.body, ...ancestorTitles)
        return (
          <View
            key={child.id}
            style={[styles.childItem, isHighlighted && styles.targetedStudyItem]}
            ref={isTarget ? targetItemRef : undefined}
          >
            <Text style={styles.childIndex}>{childIndex + 1}.</Text>
            <View style={styles.childCopy}>
              {showChildTitle || child.pageLabel ? (
                <View style={styles.itemTitleRow}>
                  {showChildTitle ? (
                    <Text style={level > 0 ? styles.grandChildTitle : styles.childTitle}>
                      {child.title}
                    </Text>
                  ) : (
                    <View style={styles.itemTitleSpacer} />
                  )}
                  {child.pageLabel ? (
                    <Text style={styles.itemPage} numberOfLines={1}>
                      {formatTextbookPageReference(child.pageLabel, 'pdf')}
                    </Text>
                  ) : null}
                </View>
              ) : null}
              <CollapsibleBody body={child.body} evidenceOnly={child.evidenceOnly} />
              <EvidenceToggle
                body={child.body}
                defaultExpanded={isTarget || isTruncatedText(child.body)}
                evidence={child.evidence}
                evidenceOnly={child.evidenceOnly}
                pageLabel={child.pageLabel}
                sectionId={sectionId}
              />
              <StudyChildList
                ancestorTitles={[...ancestorTitles, child.title]}
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
  hideHeader = false,
  highlightedItemId,
  isLast,
  onToggle,
  sectionId,
  targetItemRef,
  targetItemId,
  unitTitle,
}: {
  containsTarget: boolean
  expanded: boolean
  group: StudyGroup
  hideHeader?: boolean
  highlightedItemId?: string
  isLast: boolean
  onToggle: () => void
  sectionId: string
  targetItemRef?: RefObject<View | null>
  targetItemId?: string
  unitTitle: string
}) {
  const compact = group.items.length > 1
  const [manuallyShowAll, setManuallyShowAll] = useState(false)
  const showAll = containsTarget || manuallyShowAll

  const visibleItems = showAll ? group.items : group.items.slice(0, DEFAULT_VISIBLE_ITEMS)
  const hiddenCount = group.items.length - visibleItems.length

  return (
    <View style={[
      styles.groupBlock,
      hideHeader && styles.groupBlockWithoutHeader,
      !isLast && styles.groupDivider,
    ]}>
      {!hideHeader ? (
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
              {group.items.length} 条{group.pageLabel
                ? ` · ${formatTextbookPageReference(group.pageLabel, 'pdf')}`
                : ''}
            </Text>
          </View>
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={18}
            color={Colors.textTertiary}
          />
        </TouchableOpacity>
      ) : null}
      {hideHeader || expanded ? (
        <View style={[
          compact ? styles.numberedList : styles.singleItem,
          hideHeader && styles.listWithoutGroupHeader,
        ]}>
          {visibleItems.map((item, index) => (
            <StudyItemRow
              key={item.id}
              compact={compact}
              groupTitle={group.title}
              highlightedItemId={highlightedItemId}
              index={index}
              item={item}
              sectionId={sectionId}
              targetItemRef={targetItemRef}
              targetItemId={targetItemId}
              unitTitle={unitTitle}
            />
          ))}
          {hiddenCount > 0 ? (
            <TouchableOpacity
              style={styles.showMoreButton}
              activeOpacity={0.72}
              onPress={() => setManuallyShowAll(true)}
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
      {item.pageLabel ? (
        <Text style={styles.targetPage} testID="wrong-question-target-page">
          {formatTextbookPageReference(item.pageLabel, 'pdf')}
        </Text>
      ) : null}
      {firstEvidence ? (
        <View style={styles.targetEvidenceBox}>
          <Text style={styles.targetEvidenceLabel}>教材原文证据</Text>
          <Text style={styles.targetEvidenceText} testID="wrong-question-target-evidence">
            <Text style={styles.evidencePage}>
              （{formatTextbookPageReference(
                firstEvidence.pageLabel || item.pageLabel,
                firstEvidence.pageReferenceKind,
              )}）
            </Text>
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
  const { sectionId = '', targetItemId = '', unitId = '', from = '', via = '' } = useLocalSearchParams<{
    sectionId?: string
    targetItemId?: string
    unitId?: string
    from?: string
    via?: string
  }>()
  const fromWrongQuestion = from === 'wrong-question'
  const mapEntryAllowed = isAllowedMapUnitEntry(from, via)
  const hasTargetItem = Boolean(targetItemId)
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})
  const [dismissedHighlightId, setDismissedHighlightId] = useState<string | undefined>(undefined)
  const highlightedItemId = targetItemId && dismissedHighlightId !== targetItemId
    ? targetItemId
    : undefined
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

  useEffect(() => {
    if (!sectionId || mapEntryAllowed) return
    router.replace(buildTextbookSectionRoute(sectionId, 'map'))
  }, [mapEntryAllowed, router, sectionId])

  // G4: clear the target highlight shortly after landing
  useEffect(() => {
    if (!targetItemId) return
    const timer = setTimeout(() => setDismissedHighlightId(targetItemId), 2500)
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
          scrollView.scrollTo({ y: Math.max(0, y - Spacing.xs), animated: false })
        },
        () => {},
      )
    }, 200)
    return () => clearTimeout(timer)
  }, [hasTargetItem, targetItem])

  // G6: 仅错题定位目标组默认展开；正常进入时全部折叠，避免首屏被超长原文占满。
  const isGroupExpanded = (groupId: string) => {
    if (expandedGroups[groupId] !== undefined) return expandedGroups[groupId]
    if (targetGroupIds.has(groupId)) return true
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
    if (highlightedItemId) setDismissedHighlightId(highlightedItemId)
  }

  const returnToChapter = () => {
    if (router.canGoBack()) {
      router.back()
      return
    }
    if (from === 'map') {
      router.replace(buildKnowledgeMapRoute())
      return
    }
    router.replace(buildTextbookSectionRoute(sectionId, from || undefined))
  }

  if (!mapEntryAllowed) {
    return (
      <View style={styles.screen}>
        <Stack.Screen options={{ headerShown: false }} />
        <View style={[styles.topBar, { paddingTop: insets.top + Spacing.xs }]}>
          <ActivityIndicator color={TextbookEditorial.accent} />
          <Text style={styles.stateText}>正在返回章节目录</Text>
        </View>
      </View>
    )
  }

  return (
    <View style={styles.screen}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={[styles.topBar, { paddingTop: insets.top + Spacing.xs }]}>
        <TouchableOpacity
          style={styles.iconButton}
          onPress={returnToChapter}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="返回章节目录"
        >
          <Ionicons name="arrow-back" size={22} color={TextbookEditorial.ink} />
        </TouchableOpacity>
        <View style={styles.topCopy}>
          <Text style={styles.topEyebrow}>教材内容</Text>
          <Text style={styles.topTitle} numberOfLines={1}>
            {unit?.title || data?.section.sectionTitle || '教材小节'}
          </Text>
          {data && unit ? (
            <Text style={styles.topMeta} numberOfLines={1}>
              {data.section.sectionTitle} · {formatTextbookPageReference(
                data.section.pageRange,
                'pdf',
              )}
            </Text>
          ) : null}
        </View>
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        onScrollBeginDrag={clearHighlightOnDrag}
      >
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
            <Text style={styles.introMeta}>
              {data.partTitle} · {unit.itemCount} 条
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
                hideHeader={unit.groups.length === 1 && matchingDisplayTitle(unit.title, group.title)}
                highlightedItemId={highlightedItemId}
                isLast={index === unit.groups.length - 1}
                onToggle={() => toggleGroup(group.id)}
                sectionId={sectionId}
                targetItemRef={targetItemRef}
                targetItemId={hasTargetItem ? targetItemId : undefined}
                unitTitle={unit.title}
              />
            ))}
          </View>
        </>
      ) : null}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: TextbookEditorial.paper,
  },
  scroll: {
    flex: 1,
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
    paddingBottom: Spacing.sm,
    backgroundColor: TextbookEditorial.paper,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: TextbookEditorial.rule,
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
  topEyebrow: {
    fontSize: 11,
    lineHeight: 14,
    color: TextbookEditorial.inkFaint,
    fontFamily: TextbookEditorialFonts.ui,
  },
  topTitle: {
    fontSize: 22,
    lineHeight: 28,
    color: TextbookEditorial.ink,
    fontWeight: '600',
    fontFamily: TextbookEditorialFonts.reading,
  },
  topMeta: {
    ...Typography.labelMedium,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  unitIntro: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.sm,
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
    fontWeight: '600',
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
    fontWeight: '600',
  },
  targetTitle: {
    fontSize: 18,
    lineHeight: 25,
    color: Colors.textPrimary,
    fontWeight: '600',
    fontFamily: FontFamily.serif,
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
    fontWeight: '600',
  },
  targetEvidenceText: {
    fontSize: 16,
    lineHeight: 27,
    color: Colors.textPrimary,
    fontFamily: FontFamily.serif,
  },
  introLabel: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '600',
  },
  introTitle: {
    fontSize: 28,
    lineHeight: 36,
    color: Colors.textPrimary,
    fontWeight: '600',
    fontFamily: FontFamily.serif,
    marginTop: Spacing.xs,
  },
  introMeta: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
  groupList: {
    paddingHorizontal: Layout.screenPaddingX,
    backgroundColor: Colors.background,
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
  groupBlockWithoutHeader: {
    paddingTop: Spacing.sm,
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
    fontSize: 20,
    lineHeight: 28,
    color: Colors.textPrimary,
    fontWeight: '600',
    fontFamily: FontFamily.serif,
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
  listWithoutGroupHeader: {
    marginTop: 0,
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
    fontWeight: '600',
    fontFamily: FontFamily.serif,
  },
  childCopy: {
    flex: 1,
  },
  childTitle: {
    flex: 1,
    fontSize: 16,
    lineHeight: 25,
    color: Colors.textPrimary,
    fontWeight: '600',
    fontFamily: FontFamily.serif,
  },
  grandChildTitle: {
    flex: 1,
    fontSize: 15,
    lineHeight: 24,
    color: Colors.textPrimary,
    fontWeight: '600',
    fontFamily: FontFamily.serif,
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
    fontWeight: '600',
    fontFamily: FontFamily.serif,
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
    lineHeight: 27,
    color: Colors.textPrimary,
    fontWeight: '600',
    fontFamily: FontFamily.serif,
  },
  itemTitleSpacer: {
    flex: 1,
  },
  itemPage: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    minWidth: 54,
    flexShrink: 0,
    textAlign: 'right',
  },
  itemBody: {
    fontSize: 17,
    lineHeight: 30,
    color: Colors.textPrimary,
    fontFamily: FontFamily.serif,
    textAlign: 'left',
  },
  originalBody: {
    fontSize: 17,
    lineHeight: 30,
    color: Colors.textPrimary,
    fontFamily: FontFamily.serif,
    textAlign: 'left',
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
  fragmentBadge: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing.xs,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
    backgroundColor: 'rgba(198, 131, 43, 0.12)',
    marginBottom: Spacing.xs,
  },
  fragmentBadgeText: {
    fontSize: 11,
    lineHeight: 14,
    color: Colors.warning,
    fontWeight: '600',
  },
  bodyExpandButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    minHeight: 44,
    paddingHorizontal: Spacing.xs,
    paddingVertical: Spacing.xs,
  },
  bodyExpandText: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textTertiary,
  },
  emptyHint: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textSecondary,
    fontFamily: FontFamily.serif,
    marginTop: Spacing.xs,
  },
  evidenceBlock: {
    marginTop: Spacing.xs,
  },
  evidenceCollapsedHint: {
    // 正文与 evidence 相同时的精简容器：只保留页码入口，不重复展开正文。
    gap: Spacing.xs,
    paddingTop: Spacing.xs,
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
    textAlign: 'left',
  },
  evidenceTextBlock: {
    gap: Spacing.sm,
    paddingTop: Spacing.xs,
  },
  evidenceEntry: {
    gap: Spacing.xs,
  },
  evidenceExpandButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    minHeight: 44,
    paddingHorizontal: Spacing.xs,
    paddingVertical: Spacing.xs,
  },
  evidenceExpandText: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textTertiary,
    fontWeight: '600',
  },
  textbookPageButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    minHeight: 44,
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.sm,
    backgroundColor: Colors.primaryLight,
  },
  textbookPageButtonText: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '600',
  },
  compactPageReference: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    minHeight: 44,
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
  },
  compactPageReferenceText: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    fontWeight: '600',
    fontFamily: FontFamily.serif,
  },
  evidenceText: {
    fontSize: 16,
    lineHeight: 27,
    color: Colors.textSecondary,
    fontFamily: FontFamily.serif,
    textAlign: 'left',
  },
  evidencePage: {
    color: Colors.primary[700],
    fontWeight: '600',
    fontFamily: FontFamily.serif,
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
    fontWeight: '600',
  },
})

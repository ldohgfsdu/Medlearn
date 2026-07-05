import { useMemo, useRef, useState } from 'react'
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useRouter } from 'expo-router'
import {
  buildTextbookSectionRoute,
  buildTextbookUnitRoute,
  chapterHasCatalogOutlineUnits,
  shouldOpenChapterCatalog,
} from '@/utils/routeBuilders'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BorderRadius, Colors, FontFamily, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { INTERNAL_MEDICINE_CATALOG_PARTS } from '@/constants/internalMedicineCatalog'
import {
  formatTextbookPageReference,
  getSectionDetail,
  getTextbookTree,
} from '@/services/textbookService'
import {
  buildChapterCatalogStudyUnits,
  buildTextbookKnowledgeMap,
  resolveCatalogOutlineUnit,
  type StudyUnit,
  type TextbookMapChapter,
  type TextbookMapPart,
  type TextbookMapSubject,
} from '@/utils/textbookStudy'
import {
  formatSectionUnitTitle,
  type TextbookCatalogChapter,
} from '@/utils/knowledgeTree'

const FLOATING_TAB_BAR_BASE_HEIGHT = 74

export const options = { headerTitle: '知识地图', headerShadowVisible: false }

type ActiveChapterContext = {
  part: TextbookCatalogPartView
  chapter: TextbookCatalogChapter
  mapChapter: TextbookMapChapter | null
}

function cleanText(value: string | null | undefined): string {
  return (value ?? '').replace(/\s+/g, ' ').trim()
}

function normalizeText(value: string): string {
  return cleanText(value).replace(/\s+/g, '').replace(/[|｜　]/g, '')
}

function filterCatalog(map: TextbookMapSubject, query: string): TextbookCatalogPartView[] {
  const normalized = normalizeText(query).toLowerCase()
  const parts = INTERNAL_MEDICINE_CATALOG_PARTS.map((part) => {
    const mapPart = map.parts.find((candidate) => normalizeText(candidate.title) === normalizeText(part.chapterTitle))
    const chapters = part.sections
      .map((chapter) => ({
        catalog: chapter,
        mapChapter: mapPart?.chapters.find((candidate) => (
          normalizeText(candidate.fullTitle) === normalizeText(chapter.title)
          || normalizeText(candidate.title) === normalizeText(chapter.title)
        )) ?? null,
      }))
      .filter(({ catalog, mapChapter }) => {
        if (normalized.length < 2) return true
        const haystack = normalizeText(`${part.chapterTitle} ${catalog.title} ${catalog.units?.map((unit) => unit.title).join(' ') ?? ''}`)
          .toLowerCase()
        return haystack.includes(normalized) || Boolean(mapChapter && normalizeText(mapChapter.fullTitle).toLowerCase().includes(normalized))
      })

    return {
      title: part.chapterTitle,
      mapPart,
      chapters,
    }
  }).filter((part) => part.chapters.length > 0 || normalized.length < 2)

  return parts
}

interface TextbookCatalogPartView {
  title: string
  mapPart?: TextbookMapPart
  chapters: {
    catalog: TextbookCatalogChapter
    mapChapter: TextbookMapChapter | null
  }[]
}

function EmptyState({ text, title }: { text: string; title: string }) {
  return (
    <View style={styles.stateBlock}>
      <Ionicons name="git-branch-outline" size={28} color={Colors.neutral[300]} />
      <Text style={styles.stateTitle}>{title}</Text>
      <Text style={styles.stateText}>{text}</Text>
    </View>
  )
}

function chapterKey(partTitle: string, chapterTitle: string): string {
  return `chapter:${partTitle}:${chapterTitle}`
}

function ChapterOutlineMeta({
  catalog,
  mapChapter,
}: {
  catalog: TextbookCatalogChapter
  mapChapter: TextbookMapChapter
}) {
  const catalogUnitCount = catalog.units?.length ?? 0

  if (catalogUnitCount > 0) {
    return (
      <Text style={styles.rowMeta}>
        {catalogUnitCount}节
        {mapChapter.pageRange ? ` · ${formatTextbookPageReference(mapChapter.pageRange, 'pdf')}` : ''}
      </Text>
    )
  }

  return (
    <Text style={styles.rowMeta}>
      独立章节
      {mapChapter.pageRange ? ` · ${formatTextbookPageReference(mapChapter.pageRange, 'pdf')}` : ''}
    </Text>
  )
}

type ChapterOutlineEntry =
  | { kind: 'leaf'; key: string; title: string; studyUnit: StudyUnit | null }
  | {
      kind: 'group'
      key: string
      title: string
      subsections: { title: string; studyUnit: StudyUnit | null }[]
    }

function resolveChapterOutline(
  catalogUnits: TextbookCatalogChapter['units'],
  studyUnits: StudyUnit[],
): ChapterOutlineEntry[] {
  if (!catalogUnits?.length) {
    return studyUnits.map((studyUnit) => ({
      kind: 'leaf' as const,
      key: studyUnit.id,
      title: studyUnit.title,
      studyUnit,
    }))
  }
  return catalogUnits.map((catalogUnit) => {
    const subs = catalogUnit.subsections ?? []
    const title = formatSectionUnitTitle(catalogUnit.title)
    if (subs.length >= 2) {
      return {
        kind: 'group' as const,
        key: catalogUnit.title,
        title,
        subsections: subs.map((sub) => ({
          title: sub.title,
          studyUnit: resolveCatalogOutlineUnit(sub.title, studyUnits),
        })),
      }
    }
    const leafTitle = subs[0]?.title ?? catalogUnit.title
    const studyUnit = resolveCatalogOutlineUnit(leafTitle, studyUnits)
      ?? resolveCatalogOutlineUnit(catalogUnit.title, studyUnits)
    return { kind: 'leaf' as const, key: catalogUnit.title, title, studyUnit }
  })
}

function ChapterUnitList({
  chapter,
  mapChapter,
}: {
  chapter: TextbookCatalogChapter
  mapChapter: TextbookMapChapter
}) {
  const router = useRouter()
  const { data, error, isLoading } = useQuery({
    queryKey: ['textbookSection', mapChapter.id, 'study-units'],
    queryFn: () => getSectionDetail(mapChapter.id),
    staleTime: 300_000,
  })
  const studyUnits = useMemo(
    () => data ? buildChapterCatalogStudyUnits(data) : [],
    [data],
  )
  const outlineEntries = useMemo(
    () => resolveChapterOutline(chapter.units, studyUnits),
    [chapter.units, studyUnits],
  )

  const openUnit = (unitId: string) => {
    router.push(buildTextbookUnitRoute(mapChapter.id, unitId, { from: 'map', via: 'map-inline' }))
  }

  const renderUnitRow = (
    title: string,
    studyUnit: StudyUnit | null,
    key: string,
    isLast: boolean,
  ) => (
    <TouchableOpacity
      key={key}
      style={[
        styles.chapterUnitRow,
        isLast && styles.chapterUnitRowLast,
      ]}
      activeOpacity={0.68}
      disabled={!studyUnit}
      onPress={() => studyUnit && openUnit(studyUnit.id)}
      accessibilityRole="button"
      accessibilityLabel={`进入${title}`}
    >
      <View style={styles.chapterUnitCopy}>
        <Text style={[styles.chapterUnitTitle, !studyUnit && styles.chapterTitleMuted]}>
          {title}
        </Text>
        <Text style={styles.chapterUnitMeta}>
          {studyUnit
            ? `${formatTextbookPageReference(studyUnit.pageLabel, 'source')} · ${studyUnit.itemCount}条`
            : '内容尚未接入'}
        </Text>
      </View>
      {studyUnit ? (
        <Ionicons name="arrow-forward" size={12} color={Colors.primary[600]} />
      ) : null}
    </TouchableOpacity>
  )

  return (
    <View style={styles.chapterUnitList}>
      {isLoading ? (
        <View style={styles.chapterUnitState}>
          <ActivityIndicator size="small" color={Colors.primary[700]} />
          <Text style={styles.chapterUnitStateText}>正在读取本章小节</Text>
        </View>
      ) : null}

      {error ? (
        <Text style={styles.chapterUnitStateText}>本章小节暂时无法读取</Text>
      ) : null}

      {data ? outlineEntries.map((entry, index) => {
        if (entry.kind === 'group') {
          const isLastGroup = index === outlineEntries.length - 1
          return (
            <View key={entry.key} style={styles.chapterUnitGroup}>
              <Text style={styles.chapterUnitGroupTitle}>{entry.title}</Text>
              {entry.subsections.map((sub, subIndex) => renderUnitRow(
                sub.title,
                sub.studyUnit,
                `${entry.key}-${sub.title}`,
                isLastGroup && subIndex === entry.subsections.length - 1,
              ))}
            </View>
          )
        }
        return renderUnitRow(
          entry.title,
          entry.studyUnit,
          entry.key,
          index === outlineEntries.length - 1,
        )
      }) : null}
    </View>
  )
}

function studyUnitsQueryKey(sectionId: string) {
  return ['textbookSection', sectionId, 'study-units'] as const
}

export default function KnowledgeMapScreen() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const insets = useSafeAreaInsets()
  const openingChapterRef = useRef(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedPartKey, setExpandedPartKey] = useState<string | null>('part:第一篇 绪论')
  const [activeChapterKey, setActiveChapterKey] = useState<string | null>('chapter:第一篇 绪论:绪论')
  const [expandedChapterKey, setExpandedChapterKey] = useState<string | null>(null)

  const { data, error, isFetching, isLoading, refetch } = useQuery({
    queryKey: ['knowledgeMap', 'internal-medicine-10', 'ev1-display-contract'],
    queryFn: getTextbookTree,
    staleTime: 300_000,
  })

  const map = useMemo(() => data ? buildTextbookKnowledgeMap(data) : null, [data])
  const catalogParts = useMemo(() => map ? filterCatalog(map, '') : [], [map])
  const parts = useMemo(() => map ? filterCatalog(map, searchQuery) : [], [map, searchQuery])
  const activeContext = (() : ActiveChapterContext | null => {
    if (!activeChapterKey) return null
    for (const part of catalogParts) {
      const match = part.chapters.find(({ catalog }) => chapterKey(part.title, catalog.title) === activeChapterKey)
      if (match) {
        return {
          part,
          chapter: match.catalog,
          mapChapter: match.mapChapter,
        }
      }
    }
    return null
  })()

  const togglePart = (part: TextbookCatalogPartView) => {
    const key = `part:${part.title}`
    if (expandedPartKey === key) {
      setExpandedPartKey(null)
      return
    }

    setExpandedPartKey(key)
    const firstAvailable = part.chapters.find(({ mapChapter }) => Boolean(mapChapter)) ?? part.chapters[0]
    if (firstAvailable) {
      const firstKey = chapterKey(part.title, firstAvailable.catalog.title)
      setActiveChapterKey(firstKey)
      setExpandedChapterKey((firstAvailable.catalog.units?.length ?? 0) > 0 ? firstKey : null)
    }
  }

  const openChapterFromMap = async (mapChapter: TextbookMapChapter | null) => {
    if (!mapChapter || openingChapterRef.current) return
    openingChapterRef.current = true
    try {
      const queryKey = studyUnitsQueryKey(mapChapter.id)
      let detail = queryClient.getQueryData<Awaited<ReturnType<typeof getSectionDetail>>>(queryKey)
      if (!detail) {
        detail = await queryClient.fetchQuery({
          queryKey,
          queryFn: () => getSectionDetail(mapChapter.id),
          staleTime: 300_000,
        })
      }
      if (!detail) {
        router.push(buildTextbookSectionRoute(mapChapter.id, 'map'))
        return
      }
      const studyUnits = buildChapterCatalogStudyUnits(detail)
      if (!shouldOpenChapterCatalog(studyUnits.length)) {
        const singleUnit = studyUnits[0]
        if (!singleUnit) {
          router.push(buildTextbookSectionRoute(mapChapter.id, 'map'))
          return
        }
        router.push(buildTextbookUnitRoute(mapChapter.id, singleUnit.id, {
          from: 'map',
          via: 'catalog',
        }))
        return
      }
      router.push(buildTextbookSectionRoute(mapChapter.id, 'map'))
    } finally {
      openingChapterRef.current = false
    }
  }

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={[
          styles.content,
          { paddingBottom: FLOATING_TAB_BAR_BASE_HEIGHT + insets.bottom + Spacing.lg },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={18} color={Colors.textTertiary} />
          <TextInput
            style={styles.searchInput}
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="搜索章节或关键词..."
            placeholderTextColor={Colors.textTertiary}
            returnKeyType="search"
          />
          {searchQuery.length > 0 ? (
            <TouchableOpacity
              style={styles.clearSearch}
              activeOpacity={0.7}
              onPress={() => setSearchQuery('')}
              accessibilityRole="button"
              accessibilityLabel="清除搜索"
            >
              <Ionicons name="close" size={17} color={Colors.textSecondary} />
            </TouchableOpacity>
          ) : null}
        </View>

        {isLoading ? (
          <View style={styles.stateBlock}>
            <ActivityIndicator color={Colors.primary[700]} />
            <Text style={styles.stateText}>正在读取教材目录</Text>
          </View>
        ) : null}

        {error ? (
          <View style={styles.stateBlock}>
            <Ionicons name="alert-circle-outline" size={30} color={Colors.error} />
            <Text style={styles.stateTitle}>知识地图暂时不可用</Text>
            <Text style={styles.stateText}>本地教材视图读取失败，请重试。</Text>
            <TouchableOpacity style={styles.retryButton} disabled={isFetching} onPress={() => refetch()}>
              <Text style={styles.retryText}>{isFetching ? '重试中' : '重新读取'}</Text>
            </TouchableOpacity>
          </View>
        ) : null}

        {map ? (
          <View style={styles.catalog}>
            <View style={styles.bookRow}>
              <View style={styles.bookIcon}>
                <Ionicons name="library-outline" size={20} color={Colors.primary[600]} />
              </View>
              <View style={styles.bookCopy}>
                <Text style={styles.bookTitle}>{map.title}</Text>
                <Text style={styles.bookMeta}>{map.partCount} 篇 · {map.chapterCount} 章</Text>
              </View>
            </View>

            <View style={styles.partList}>
              {parts.map((part) => {
                const partKey = `part:${part.title}`
                const partExpanded = expandedPartKey === partKey
                const partIsCurrent = activeContext?.part.title === part.title

                if (!partExpanded) {
                  return (
                    <Pressable
                      key={part.title}
                      style={({ pressed }) => [styles.collapsedPartRow, pressed && styles.pressed]}
                      accessibilityRole="button"
                      accessibilityState={{ expanded: false }}
                      onPress={() => togglePart(part)}
                    >
                      <View style={styles.partMarkerBar} />
                      <Text style={styles.collapsedPartTitle} numberOfLines={1}>
                        {part.title}
                      </Text>
                      <Ionicons name="chevron-forward" size={14} color={Colors.textTertiary} />
                    </Pressable>
                  )
                }

                return (
                  <View key={part.title} style={styles.expandedPartCard}>
                    <Pressable
                      style={({ pressed }) => [styles.expandedPartHeader, pressed && styles.pressed]}
                      accessibilityRole="button"
                      accessibilityState={{ expanded: true }}
                      onPress={() => togglePart(part)}
                    >
                      <View style={[styles.partMarkerBar, styles.partMarkerBarActive]} />
                      <Text
                        style={styles.expandedPartTitle}
                        numberOfLines={1}
                      >
                        {part.title}
                      </Text>
                      {partIsCurrent ? (
                        <Text style={styles.currentBadge}>当前篇章</Text>
                      ) : null}
                    </Pressable>

                    {partIsCurrent && activeContext ? (
                      <Text
                        numberOfLines={1}
                        style={styles.breadcrumb}
                        accessibilityLabel={`当前位置：${map.title}，${part.title}，${activeContext.chapter.title}`}
                      >
                        {map.title} / {part.title} / {activeContext.chapter.title}
                      </Text>
                    ) : null}

                    <View style={styles.chapterList}>
                      {part.chapters.map(({ catalog, mapChapter }) => {
                        const key = chapterKey(part.title, catalog.title)
                        const chapterActive = activeChapterKey === key
                        const hasCatalogUnits = chapterHasCatalogOutlineUnits(catalog)
                        const available = Boolean(mapChapter)
                        const chapterExpanded = expandedChapterKey === key
                        const chapterChevron = chapterActive && available && hasCatalogUnits && chapterExpanded
                          ? 'chevron-down'
                          : 'chevron-forward'

                        return (
                          <View
                            key={catalog.title}
                            style={[
                              styles.chapterBlock,
                              catalog.title === part.chapters[part.chapters.length - 1]?.catalog.title
                                && !(chapterActive && chapterExpanded)
                                && styles.chapterBlockLast,
                            ]}
                          >
                            <Pressable
                              style={({ pressed }) => [
                                styles.chapterRow,
                                pressed && styles.pressed,
                              ]}
                              accessibilityRole="button"
                              accessibilityState={{
                                selected: chapterActive,
                                expanded: hasCatalogUnits ? chapterExpanded : undefined,
                              }}
                              onPress={() => {
                                if (!available) {
                                  setActiveChapterKey(key)
                                  setExpandedChapterKey(null)
                                  return
                                }
                                if (!hasCatalogUnits) {
                                  void openChapterFromMap(mapChapter)
                                  return
                                }
                                setActiveChapterKey(key)
                                setExpandedChapterKey(chapterExpanded ? null : key)
                              }}
                              accessibilityLabel={
                                !available
                                  ? `${catalog.title}暂无内容`
                                  : !hasCatalogUnits
                                    ? `进入${catalog.title}`
                                    : `展开${catalog.title}`
                              }
                            >
                              <View
                                style={[
                                  styles.chapterMarkerBar,
                                  chapterActive && available && styles.chapterMarkerBarActive,
                                ]}
                              />
                              <View style={styles.rowCopy}>
                                <Text
                                  numberOfLines={!available ? 2 : 1}
                                  style={[
                                    styles.chapterTitle,
                                    chapterActive && available && styles.chapterTitleActive,
                                    !available && styles.chapterTitleMuted,
                                  ]}
                                >
                                  {catalog.title}
                                </Text>
                                {mapChapter ? (
                                  <ChapterOutlineMeta catalog={catalog} mapChapter={mapChapter} />
                                ) : (
                                  <Text style={styles.rowMeta}>暂无内容</Text>
                                )}
                              </View>
                              {chapterActive && !available ? (
                                <Text style={styles.chapterStatus}>暂无内容</Text>
                              ) : (
                                <Ionicons
                                  name={chapterChevron}
                                  size={14}
                                  color={chapterActive && available ? Colors.primary[600] : Colors.textTertiary}
                                />
                              )}
                            </Pressable>

                            {chapterActive && chapterExpanded && mapChapter ? (
                              <ChapterUnitList chapter={catalog} mapChapter={mapChapter} />
                            ) : null}
                          </View>
                        )
                      })}
                    </View>
                  </View>
                )
              })}
            </View>
          </View>
        ) : null}

        {map && parts.length === 0 ? (
          <EmptyState title="没有匹配的教材目录" text="换一个更接近教材目录的关键词。" />
        ) : null}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  pressed: {
    opacity: 0.72,
    transform: [{ scale: 0.99 }],
  },
  content: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingTop: Spacing.base,
    // paddingBottom 由 inline（FLOATING_TAB_BAR_BASE_HEIGHT + insets.bottom + Spacing.lg）提供，
    // 为浮动 TabBar 留出 safe area。
    gap: Spacing.base,
  },
  searchBox: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.base,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  searchInput: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    paddingVertical: Spacing.sm,
  },
  clearSearch: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: -Spacing.sm,
  },
  // -- 临床编辑目录 --
  catalog: {
    gap: Spacing.md,
  },
  bookRow: {
    minHeight: 64,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.base,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
  },
  bookIcon: {
    width: 40,
    height: 40,
    borderRadius: BorderRadius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
  },
  bookCopy: {
    flex: 1,
    minWidth: 0,
  },
  bookTitle: {
    ...Typography.titleSmall,
    fontSize: 16,
    lineHeight: 20,
    fontWeight: '600',
    color: Colors.textPrimary,
    fontFamily: FontFamily.serif,
  },
  bookMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 1,
  },
  partList: {
    gap: Spacing.xs,
    paddingTop: Spacing.xs,
  },
  collapsedPartRow: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.sm,
  },
  collapsedPartTitle: {
    flex: 1,
    minWidth: 0,
    ...Typography.titleSmall,
    fontSize: 16,
    lineHeight: 20,
    fontWeight: '500',
    color: Colors.textSecondary,
    fontFamily: FontFamily.serif,
  },
  expandedPartCard: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.background,
    overflow: 'hidden',
    marginVertical: Spacing.xs,
  },
  expandedPartHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.base,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  partMarkerBar: {
    width: 3,
    height: 18,
    borderRadius: 2,
    backgroundColor: Colors.border,
  },
  partMarkerBarActive: {
    backgroundColor: Colors.primary[600],
  },
  expandedPartTitle: {
    flex: 1,
    minWidth: 0,
    ...Typography.titleSmall,
    fontSize: 16,
    lineHeight: 20,
    fontWeight: '500',
    color: Colors.textPrimary,
    fontFamily: FontFamily.serif,
  },
  currentBadge: {
    ...Typography.labelSmall,
    color: Colors.primary[600],
    backgroundColor: Colors.primary[50],
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.full,
    overflow: 'hidden',
  },
  breadcrumb: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    paddingHorizontal: Spacing.base,
    paddingBottom: Spacing.sm,
  },
  chapterList: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  chapterBlock: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  chapterBlockLast: {
    borderBottomWidth: 0,
  },
  chapterRow: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.md,
  },
  chapterMarkerBar: {
    width: 2,
    height: 12,
    borderRadius: 1,
    backgroundColor: Colors.border,
  },
  chapterMarkerBarActive: {
    backgroundColor: Colors.primary[600],
  },
  chapterTitle: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    fontFamily: FontFamily.serif,
  },
  chapterTitleActive: {
    color: Colors.textPrimary,
  },
  chapterTitleMuted: {
    color: Colors.textTertiary,
  },
  chapterStatus: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  chapterUnitList: {
    marginLeft: 22,
    paddingLeft: Spacing.lg,
    paddingRight: Spacing.base,
    paddingBottom: Spacing.sm,
    borderLeftWidth: 2,
    borderLeftColor: Colors.border,
  },
  chapterUnitState: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingRight: Spacing.md,
  },
  chapterUnitStateText: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    paddingVertical: Spacing.md,
  },
  chapterUnitRow: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  chapterUnitRowLast: {
    borderBottomWidth: 0,
  },
  chapterUnitGroup: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  chapterUnitGroupTitle: {
    ...Typography.bodySmall,
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textTertiary,
    fontFamily: FontFamily.serif,
    fontWeight: '600',
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xs,
  },
  chapterUnitCopy: {
    flex: 1,
    minWidth: 0,
  },
  chapterUnitTitle: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    fontWeight: '500',
    fontFamily: FontFamily.serif,
  },
  chapterUnitMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 1,
  },
  enterAction: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.md,
    marginRight: Spacing.xs,
  },
  enterActionText: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
    fontWeight: '600',
  },
  rowCopy: {
    flex: 1,
    minWidth: 0,
  },
  rowCopyWithTag: {
    flex: 1,
    minWidth: 0,
    paddingRight: Spacing.sm,
  },
  rowMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  stateBlock: {
    minHeight: 160,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    padding: Spacing.xl,
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
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.lg,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[700],
    marginTop: Spacing.sm,
  },
  retryText: {
    ...Typography.labelLarge,
    color: Colors.surface,
    fontWeight: '500',
  },
})

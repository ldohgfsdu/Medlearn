import { useMemo, useState } from 'react'
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  type StyleProp,
  type TextStyle,
  View,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, type Href, useRouter } from 'expo-router'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BorderRadius, Colors, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { INTERNAL_MEDICINE_CATALOG_PARTS } from '@/constants/internalMedicineCatalog'
import { getSectionDetail, getTextbookTree } from '@/services/textbookService'
import {
  buildChapterStudyUnits,
  buildTextbookKnowledgeMap,
  type StudyGroup,
  type StudyUnit,
  type TextbookMapChapter,
  type TextbookMapPart,
  type TextbookMapSubject,
} from '@/utils/textbookStudy'
import {
  extractChapterLabel,
  extractSectionUnitEntity,
  formatSectionUnitTitle,
  type TextbookCatalogChapter,
  type TextbookCatalogSubsection,
  type TextbookCatalogUnit,
} from '@/utils/knowledgeTree'

export const options = { headerTitle: '知识地图' }

type ExpandedState = Record<string, boolean>

type CatalogEntryTarget = {
  chapter: TextbookCatalogChapter
  mapChapter: TextbookMapChapter | null
  subsection?: TextbookCatalogSubsection
  unit?: TextbookCatalogUnit
}

type CatalogTitleParts = {
  ordinal: string | null
  title: string
}

function cleanText(value: string | null | undefined): string {
  return (value ?? '').replace(/\s+/g, ' ').trim()
}

function normalizeText(value: string): string {
  return cleanText(value).replace(/\s+/g, '').replace(/[|｜　]/g, '')
}

function stripOrdinal(value: string): string {
  return cleanText(value)
    .replace(/^第[一二三四五六七八九十百零〇\d]+篇\s*/u, '')
    .replace(/^第[一二三四五六七八九十百零〇\d]+章\s*/u, '')
    .replace(/^第[一二三四五六七八九十百零〇\d]+节\s*[|｜]?\s*/u, '')
    .replace(/^[一二三四五六七八九十百零〇\d]+[、.．]\s*/u, '')
    .trim()
}

function splitCatalogTitle(value: string): CatalogTitleParts {
  const title = cleanText(value).replace(/\s*[|｜]\s*/u, ' ')
  const match = title.match(/^(第[一二三四五六七八九十百零〇\d]+[篇章节])\s*(.+)$/u)
  if (!match) return { ordinal: null, title }
  return { ordinal: match[1], title: match[2].trim() }
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

function catalogUnitLeafTitle(unit: TextbookCatalogUnit): CatalogTitleParts {
  return splitCatalogTitle(formatSectionUnitTitle(unit.title))
}

function chapterLeafTitle(chapter: TextbookCatalogChapter): string {
  return extractChapterLabel(chapter.title) || stripOrdinal(chapter.title)
}

function subsectionIsRedundant(unit: TextbookCatalogUnit, subsection: TextbookCatalogSubsection): boolean {
  return normalizeText(stripOrdinal(extractSectionUnitEntity(unit.title))) === normalizeText(subsection.title)
}

function groupsForSubsection(unit: StudyUnit, subsectionTitle: string): StudyGroup[] {
  const normalized = normalizeText(subsectionTitle)
  return unit.groups.filter((group) => normalizeText(stripOrdinal(group.title)).includes(normalized)
    || normalized.includes(normalizeText(stripOrdinal(group.title))))
}

function findMatchingUnit(units: StudyUnit[], options: {
  chapterTitle: string
  subsectionTitle?: string
  unitTitle?: string
}): StudyUnit | null {
  const unitTitle = options.unitTitle ? normalizeText(extractSectionUnitEntity(options.unitTitle)) : ''
  const subsectionTitle = options.subsectionTitle ? normalizeText(options.subsectionTitle) : ''
  const chapterTitle = normalizeText(chapterLeafTitle({ title: options.chapterTitle }))

  return units.find((unit) => unitTitle && normalizeText(unit.title).includes(unitTitle))
    ?? units.find((unit) => subsectionTitle && normalizeText(unit.title).includes(subsectionTitle))
    ?? units.find((unit) => chapterTitle && normalizeText(unit.title).includes(chapterTitle))
    ?? units[0]
    ?? null
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

function TreeChevron({ expanded, visible }: { expanded: boolean; visible: boolean }) {
  if (!visible) return <View style={styles.chevronSlot} />
  return (
    <View style={styles.chevronSlot}>
      <Ionicons
        name={expanded ? 'chevron-down' : 'chevron-forward'}
        size={16}
        color={Colors.textTertiary}
      />
    </View>
  )
}

function TreeMarker({ kind = 'leaf' }: { kind?: 'leaf' | 'branch' }) {
  return (
    <View style={styles.markerSlot}>
      <View style={[styles.leafDot, kind === 'branch' && styles.branchDot]} />
    </View>
  )
}

function CatalogTitle({
  numberOfLines,
  parts,
  style,
}: {
  numberOfLines?: number
  parts: CatalogTitleParts
  style: StyleProp<TextStyle>
}) {
  if (!parts.ordinal) {
    return (
      <Text numberOfLines={numberOfLines} style={style}>
        {parts.title}
      </Text>
    )
  }

  return (
    <View style={styles.catalogTitleRow}>
      <Text style={[style, styles.catalogTitleOrdinal]}>{parts.ordinal}</Text>
      <View style={styles.catalogTitleNameColumn}>
        <Text numberOfLines={numberOfLines} style={[style, styles.catalogTitleName]}>
          {parts.title}
        </Text>
      </View>
    </View>
  )
}

function ContentStatusTag({ available }: { available: boolean }) {
  return (
    <View style={[styles.statusTag, available ? styles.statusTagReady : styles.statusTagMuted]}>
      <Text style={[styles.statusTagText, available ? styles.statusTagTextReady : styles.statusTagTextMuted]}>
        {available ? '可学习' : '暂无内容'}
      </Text>
    </View>
  )
}

function ChapterFocusPanel({
  chapter,
  expanded,
  mapChapter,
  onOpen,
  onToggle,
  openingKey,
}: {
  chapter: TextbookCatalogChapter
  expanded: ExpandedState
  mapChapter: TextbookMapChapter | null
  onOpen: (target: CatalogEntryTarget) => Promise<void>
  onToggle: (key: string) => void
  openingKey: string | null
}) {
  const units = chapter.units ?? []
  const hasCatalogUnits = units.length > 0
  const available = Boolean(mapChapter)
  const chapterOpening = openingKey?.startsWith(`${mapChapter?.id}:`)
  const leafMeta = available ? '进入知识点详情' : '暂未整理'
  const sectionMeta = available ? '进入知识点详情' : '暂未整理'

  return (
    <View style={styles.focusPanel}>
      <View style={styles.focusHeader}>
        <View style={styles.focusHeaderCopy}>
          <Text style={styles.focusEyebrow}>
            {hasCatalogUnits ? `本章目录 · ${units.length} 节` : '独立章节 · 1 个入口'}
          </Text>
        </View>
        <ContentStatusTag available={available} />
      </View>

      {!available ? (
        <Text style={styles.focusNotice}>当前仅保留目录结构，内容整理后开放详情。</Text>
      ) : null}

      {!hasCatalogUnits ? (
        <TouchableOpacity
          style={styles.focusLeafRow}
          activeOpacity={0.74}
          disabled={!available || Boolean(openingKey)}
          onPress={() => onOpen({ chapter, mapChapter })}
        >
          <TreeMarker />
          <View style={styles.rowCopy}>
            <Text style={styles.focusLeafTitle}>{chapterLeafTitle(chapter)}</Text>
            <Text style={styles.rowMeta}>{leafMeta}</Text>
          </View>
          {chapterOpening ? (
            <ActivityIndicator size="small" color={Colors.primary[700]} />
          ) : available ? (
            <Ionicons name="arrow-forward" size={15} color={available ? Colors.primary[700] : Colors.textTertiary} />
          ) : null}
        </TouchableOpacity>
      ) : null}

      {hasCatalogUnits ? units.map((unit) => {
        const subsections = unit.subsections ?? []
        const shouldExpandSubsections = subsections.length > 1
          || (subsections.length === 1 && !subsectionIsRedundant(unit, subsections[0]))
        const unitKey = `unit:${chapter.title}:${unit.title}`
        const unitExpanded = Boolean(expanded[unitKey])
        const unitOpening = openingKey?.includes(unit.title)

        return (
          <View key={unit.title} style={styles.focusGroup}>
            <TouchableOpacity
              style={[styles.focusLeafRow, shouldExpandSubsections && unitExpanded && styles.focusLeafRowOpen]}
              activeOpacity={0.74}
              disabled={!shouldExpandSubsections && (!available || Boolean(openingKey))}
              onPress={() => (
                shouldExpandSubsections
                  ? onToggle(unitKey)
                  : onOpen({ chapter, mapChapter, unit, subsection: subsections[0] })
              )}
            >
              <TreeMarker kind={shouldExpandSubsections ? 'branch' : 'leaf'} />
              <View style={styles.rowCopy}>
                <CatalogTitle parts={catalogUnitLeafTitle(unit)} style={styles.focusLeafTitle} />
                <Text style={styles.rowMeta}>
                  {shouldExpandSubsections ? `${subsections.length} 小节` : leafMeta}
                </Text>
              </View>
              {unitOpening ? (
                <ActivityIndicator size="small" color={Colors.primary[700]} />
              ) : shouldExpandSubsections ? (
                <Ionicons
                  name={unitExpanded ? 'chevron-down' : 'chevron-forward'}
                  size={17}
                  color={Colors.textTertiary}
                />
              ) : available ? (
                <Ionicons name="arrow-forward" size={15} color={Colors.primary[700]} />
              ) : null}
            </TouchableOpacity>

            {unitExpanded && shouldExpandSubsections ? subsections.map((subsection, index) => {
              const subsectionOpening = openingKey?.includes(subsection.title)
              return (
                <TouchableOpacity
                  key={`${unit.title}:${subsection.title}`}
                  style={styles.focusSubRow}
                  activeOpacity={0.74}
                  disabled={!available || Boolean(openingKey)}
                  onPress={() => onOpen({ chapter, mapChapter, unit, subsection })}
                >
                  <TreeMarker />
                  <View style={styles.rowCopy}>
                    <Text style={styles.subsectionTitle}>{subsection.title}</Text>
                    <Text style={styles.rowMeta}>{sectionMeta}</Text>
                  </View>
                  {subsectionOpening ? (
                    <ActivityIndicator size="small" color={Colors.primary[700]} />
                  ) : available ? (
                    <Ionicons name="arrow-forward" size={15} color={available ? Colors.primary[700] : Colors.textTertiary} />
                  ) : null}
                </TouchableOpacity>
              )
            }) : null}
          </View>
        )
      }) : null}
    </View>
  )
}

export default function KnowledgeMapScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [expanded, setExpanded] = useState<ExpandedState>({ book: true })
  const [activeChapterKey, setActiveChapterKey] = useState<string | null>(null)
  const [openingKey, setOpeningKey] = useState<string | null>(null)

  const { data, error, isFetching, isLoading, refetch } = useQuery({
    queryKey: ['knowledgeMap', 'internal-medicine-10', 'ev1-display-contract'],
    queryFn: getTextbookTree,
    staleTime: 300_000,
  })

  const map = useMemo(() => data ? buildTextbookKnowledgeMap(data) : null, [data])
  const parts = useMemo(() => map ? filterCatalog(map, searchQuery) : [], [map, searchQuery])

  const toggle = (key: string) => {
    setExpanded((current) => ({ ...current, [key]: !current[key] }))
  }

  const selectChapter = (key: string) => {
    setActiveChapterKey((current) => (current === key ? null : key))
  }

  const openCatalogEntry = async ({
    chapter,
    mapChapter,
    subsection,
    unit,
  }: CatalogEntryTarget) => {
    if (!mapChapter) return

    const openingId = `${mapChapter.id}:${unit?.title ?? chapter.title}:${subsection?.title ?? ''}`
    setOpeningKey(openingId)
    try {
      const detail = await queryClient.fetchQuery({
        queryKey: ['knowledgeMapChapterDetail', mapChapter.id],
        queryFn: () => getSectionDetail(mapChapter.id),
        staleTime: 300_000,
      })
      if (!detail) return

      const studyUnits = buildChapterStudyUnits(detail)
      const targetUnit = findMatchingUnit(studyUnits, {
        chapterTitle: chapter.title,
        subsectionTitle: subsection?.title,
        unitTitle: unit?.title,
      })
      if (!targetUnit) return

      const matchedGroup = subsection ? groupsForSubsection(targetUnit, subsection.title)[0] : null
      const targetItemId = matchedGroup?.items[0]?.id
      router.push({
        pathname: '/textbook/[sectionId]/unit/[unitId]',
        params: {
          sectionId: mapChapter.id,
          unitId: targetUnit.id,
          from: 'map',
          ...(targetItemId ? { targetItemId } : {}),
        },
      } as unknown as Href)
    } finally {
      setOpeningKey(null)
    }
  }

  return (
    <View style={styles.screen}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={[styles.topBar, { paddingTop: insets.top + Spacing.xs }]}>
        <Pressable
          style={({ pressed }) => [styles.topIconButton, pressed && styles.pressed]}
          accessibilityRole="button"
          accessibilityLabel="返回"
          onPress={() => (router.canGoBack() ? router.back() : router.replace('/(tabs)' as Href))}
        >
          <Ionicons name="arrow-back" size={22} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.topTitle}>知识地图</Text>
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={18} color={Colors.textTertiary} />
          <TextInput
            style={styles.searchInput}
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="搜索教材目录，例如 呼吸系统、肺部感染"
            placeholderTextColor={Colors.textTertiary}
            returnKeyType="search"
          />
          {searchQuery.length > 0 ? (
            <TouchableOpacity style={styles.clearSearch} activeOpacity={0.7} onPress={() => setSearchQuery('')}>
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
          <View style={styles.treeCard}>
            <Pressable
              style={({ pressed }) => [styles.bookRow, pressed && styles.pressed]}
              accessibilityRole="button"
              accessibilityState={{ expanded: Boolean(expanded.book) }}
              onPress={() => toggle('book')}
            >
              <TreeChevron expanded={Boolean(expanded.book)} visible />
              <View style={styles.bookIcon}>
                <Ionicons name="library-outline" size={20} color={Colors.primary[700]} />
              </View>
              <View style={styles.rowCopy}>
                <Text style={styles.bookTitle}>{map.title}</Text>
                <Text style={styles.rowMeta}>{map.partCount} 篇 · {map.chapterCount} 章 · 教材目录</Text>
              </View>
            </Pressable>

            {expanded.book ? parts.map((part, partIndex) => {
              const partKey = `part:${part.title}`
              const partExpanded = Boolean(expanded[partKey])
              return (
                <View key={part.title}>
                  <Pressable
                    style={({ pressed }) => [styles.partRow, pressed && styles.pressed]}
                    accessibilityRole="button"
                    accessibilityState={{ expanded: partExpanded }}
                    onPress={() => toggle(partKey)}
                  >
                    <TreeChevron expanded={partExpanded} visible={part.chapters.length > 0} />
                    <View style={styles.treeLine} />
                    <View style={styles.rowCopy}>
                      <Text style={styles.partTitle}>{part.title}</Text>
                      <Text style={styles.rowMeta}>
                        {part.mapPart?.chapterCount ?? part.chapters.length} 章{part.mapPart?.pageRange ? ` · p.${part.mapPart.pageRange}` : ''}
                      </Text>
                    </View>
                  </Pressable>

                  {partExpanded ? part.chapters.map(({ catalog, mapChapter }) => {
                    const chapterKey = `chapter:${part.title}:${catalog.title}`
                    const chapterActive = activeChapterKey === chapterKey
                    const units = catalog.units ?? []
                    const hasCatalogUnits = units.length > 0
                    return (
                      <View key={catalog.title}>
                        <Pressable
                          style={({ pressed }) => [
                            styles.chapterRow,
                            chapterActive && styles.chapterRowActive,
                            pressed && styles.pressed,
                          ]}
                          accessibilityRole="button"
                          accessibilityState={{ expanded: chapterActive }}
                          onPress={() => selectChapter(chapterKey)}
                        >
                          <TreeChevron expanded={chapterActive} visible />
                          <View style={styles.chapterIndent} />
                          <View style={styles.chapterDot} />
                          <View style={styles.rowCopyWithTag}>
                            <Text numberOfLines={!mapChapter ? 2 : undefined} style={styles.chapterTitle}>{catalog.title}</Text>
                            <Text style={styles.rowMeta}>
                              {hasCatalogUnits ? `${units.length} 节` : '独立章节'}
                              {mapChapter?.pageRange ? ` · p.${mapChapter.pageRange}` : ''}
                            </Text>
                          </View>
                          {!mapChapter ? <ContentStatusTag available={false} /> : null}
                        </Pressable>

                        {chapterActive ? (
                          <ChapterFocusPanel
                            chapter={catalog}
                            expanded={expanded}
                            mapChapter={mapChapter}
                            onOpen={openCatalogEntry}
                            onToggle={toggle}
                            openingKey={openingKey}
                          />
                        ) : null}
                      </View>
                    )
                  }) : null}

                  {partIndex < parts.length - 1 ? <View style={styles.partDivider} /> : null}
                </View>
              )
            }) : null}
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
  topBar: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Spacing.xs,
    gap: Spacing.md,
    backgroundColor: Colors.background,
  },
  topTitle: {
    flex: 1,
    fontSize: 28,
    lineHeight: 34,
    color: Colors.textPrimary,
    fontWeight: '800',
  },
  topIconButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 22,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  pressed: {
    opacity: 0.72,
    transform: [{ scale: 0.99 }],
  },
  content: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Layout.screenPaddingBottom,
    gap: Spacing.md,
  },
  searchBox: {
    minHeight: 46,
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
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  treeCard: {
    overflow: 'hidden',
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  bookRow: {
    minHeight: 70,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  bookIcon: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
  },
  bookTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  partRow: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
  },
  partTitle: {
    fontSize: 16,
    lineHeight: 22,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  partDivider: {
    height: StyleSheet.hairlineWidth,
    marginLeft: 48,
    backgroundColor: Colors.border,
  },
  chapterRow: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingLeft: Spacing.sm,
    paddingRight: Spacing.md,
    borderLeftWidth: 3,
    borderLeftColor: 'transparent',
  },
  chapterRowActive: {
    backgroundColor: Colors.surface,
    borderLeftColor: Colors.primary[500],
  },
  chapterIndent: {
    width: 10,
    alignSelf: 'stretch',
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderLeftColor: Colors.border,
  },
  chapterDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.primary[300],
  },
  chapterTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  leafRow: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingLeft: Spacing.md,
    paddingRight: Spacing.md,
  },
  leafIndent: {
    width: 44,
    alignSelf: 'stretch',
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderLeftColor: Colors.border,
  },
  leafIndentSmall: {
    width: 22,
    alignSelf: 'stretch',
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderLeftColor: Colors.border,
  },
  leafDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: Colors.primary[600],
  },
  branchDot: {
    backgroundColor: Colors.primary[400],
  },
  leafTitle: {
    fontSize: 15,
    lineHeight: 22,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  subsectionRow: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingLeft: Spacing.md,
    paddingRight: Spacing.md,
  },
  subsectionIndent: {
    width: 72,
    alignSelf: 'stretch',
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderLeftColor: Colors.border,
  },
  subsectionOrdinal: {
    width: 22,
    ...Typography.labelMedium,
    color: Colors.primary[700],
    fontWeight: '800',
  },
  subsectionTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '700',
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
  catalogTitleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    flex: 1,
    minWidth: 0,
  },
  catalogTitleOrdinal: {
    width: 56,
    flexShrink: 0,
    marginRight: Spacing.sm,
  },
  catalogTitleNameColumn: {
    flex: 1,
    minWidth: 0,
  },
  catalogTitleName: {
    flexShrink: 1,
  },
  statusTag: {
    minHeight: 24,
    justifyContent: 'center',
    borderRadius: BorderRadius.full,
    paddingHorizontal: Spacing.sm,
    borderWidth: 1,
    flexShrink: 0,
    marginLeft: Spacing.xs,
  },
  statusTagReady: {
    backgroundColor: Colors.primary[50],
    borderColor: Colors.primary[100],
  },
  statusTagMuted: {
    backgroundColor: Colors.neutral[100],
    borderColor: Colors.neutral[200],
  },
  statusTagText: {
    ...Typography.labelSmall,
    fontWeight: '700',
  },
  statusTagTextReady: {
    color: Colors.primary[700],
  },
  statusTagTextMuted: {
    color: Colors.textSecondary,
  },
  focusPanel: {
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.primary[100],
    backgroundColor: Colors.surface,
    overflow: 'hidden',
  },
  focusHeader: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.primary[50],
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.primary[100],
  },
  focusHeaderCopy: {
    flex: 1,
    minWidth: 0,
  },
  focusEyebrow: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '800',
  },
  focusTitle: {
    fontSize: 17,
    lineHeight: 23,
    color: Colors.textPrimary,
    fontWeight: '800',
    marginTop: 1,
  },
  focusNotice: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  focusGroup: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  focusLeafRow: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
  },
  focusLeafRowOpen: {
    backgroundColor: Colors.neutral[50],
  },
  focusLeafTitle: {
    fontSize: 15,
    lineHeight: 22,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  focusSubRow: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingLeft: Spacing.xl,
    paddingRight: Spacing.md,
    paddingVertical: Spacing.xs,
    backgroundColor: Colors.neutral[50],
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  markerSlot: {
    width: 20,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chevronSlot: {
    width: 20,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  treeLine: {
    width: 8,
    alignSelf: 'stretch',
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderLeftColor: Colors.border,
  },
  disabledRow: {
    opacity: 1,
  },
  disabledText: {
    color: Colors.textSecondary,
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
    fontWeight: '700',
  },
})

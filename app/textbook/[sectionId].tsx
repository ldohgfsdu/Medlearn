import { useEffect, useMemo, useRef } from 'react'
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, useLocalSearchParams, useRouter } from 'expo-router'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useQuery } from '@tanstack/react-query'
import { TextbookEditorial, TextbookEditorialFonts } from '@/constants/textbookEditorial'
import { Colors, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { buildKnowledgeMapRoute, buildTextbookUnitRoute } from '@/utils/routeBuilders'
import { INTERNAL_MEDICINE_CATALOG_PARTS } from '@/constants/internalMedicineCatalog'
import {
  formatTextbookPageReference,
  getRespiratorySectionTitle,
  getSectionDetail,
} from '@/services/textbookService'
import {
  buildChapterCatalogStudyUnits,
  resolveCatalogOutlineUnit,
  type StudyUnit,
} from '@/utils/textbookStudy'
import {
  formatSectionUnitTitle,
  type TextbookCatalogChapter,
  type TextbookCatalogUnit,
} from '@/utils/knowledgeTree'

type CatalogOutlineSubsection = {
  title: string
  studyUnit: StudyUnit | null
}

type CatalogOutlineEntry = {
  catalogUnit: TextbookCatalogUnit
  kind: 'leaf' | 'group'
  studyUnit: StudyUnit | null
  subsections: CatalogOutlineSubsection[]
}

function normalizeCatalogText(value: string): string {
  return value.replace(/\s+/g, '').replace(/[|｜　]/g, '')
}

function findCatalogChapter(sectionTitle: string): TextbookCatalogChapter | null {
  for (const part of INTERNAL_MEDICINE_CATALOG_PARTS) {
    const chapter = part.sections.find(
      (candidate) => normalizeCatalogText(candidate.title) === normalizeCatalogText(sectionTitle),
    )
    if (chapter) return chapter
  }
  return null
}

function buildSectionOutlineEntries(
  catalogUnits: TextbookCatalogUnit[],
  studyUnits: StudyUnit[],
): CatalogOutlineEntry[] {
  return catalogUnits.map((catalogUnit) => {
    const subs = catalogUnit.subsections ?? []
    if (subs.length >= 2) {
      return {
        catalogUnit,
        kind: 'group' as const,
        studyUnit: null,
        subsections: subs.map((sub) => ({
          title: sub.title,
          studyUnit: resolveCatalogOutlineUnit(sub.title, studyUnits),
        })),
      }
    }
    const leafTitle = subs[0]?.title ?? catalogUnit.title
    const studyUnit = resolveCatalogOutlineUnit(leafTitle, studyUnits)
      ?? resolveCatalogOutlineUnit(catalogUnit.title, studyUnits)
    return { catalogUnit, kind: 'leaf' as const, studyUnit, subsections: [] }
  })
}

function UnitRow({
  entry,
  onPressUnit,
}: {
  entry: CatalogOutlineEntry
  onPressUnit: (studyUnit: StudyUnit) => void
}) {
  if (entry.kind === 'group') {
    return (
      <View style={styles.unitBlock}>
        <Text style={styles.unitGroupTitle}>{formatSectionUnitTitle(entry.catalogUnit.title)}</Text>
        <View style={styles.subsectionList}>
          {entry.subsections.map((subsection) => (
            <TouchableOpacity
              key={subsection.title}
              style={styles.subsectionRow}
              activeOpacity={0.68}
              disabled={!subsection.studyUnit}
              onPress={() => subsection.studyUnit && onPressUnit(subsection.studyUnit)}
              accessibilityRole="button"
              accessibilityLabel={`进入${subsection.title}`}
            >
              <View style={styles.subsectionDot} />
              <View style={styles.subsectionCopy}>
                <Text
                  style={[styles.subsectionTitle, !subsection.studyUnit && styles.subsectionTitleMuted]}
                >
                  {subsection.title}
                </Text>
                {subsection.studyUnit ? (
                  <Text style={styles.subsectionMeta}>
                    {formatTextbookPageReference(subsection.studyUnit.pageLabel, 'source')} · {subsection.studyUnit.itemCount} 条
                  </Text>
                ) : null}
              </View>
              {subsection.studyUnit ? (
                <Ionicons name="chevron-forward" size={16} color={TextbookEditorial.inkFaint} />
              ) : null}
            </TouchableOpacity>
          ))}
        </View>
      </View>
    )
  }

  const { studyUnit } = entry
  return (
    <View style={styles.unitBlock}>
      <TouchableOpacity
        style={styles.unitRow}
        activeOpacity={0.68}
        disabled={!studyUnit}
        onPress={() => studyUnit && onPressUnit(studyUnit)}
        accessibilityRole="button"
        accessibilityLabel={`进入${formatSectionUnitTitle(entry.catalogUnit.title)}`}
      >
        <View style={styles.unitCopy}>
          <Text style={[styles.unitTitle, !studyUnit && styles.unitTitleMuted]}>
            {formatSectionUnitTitle(entry.catalogUnit.title)}
          </Text>
          <Text style={styles.unitMeta}>
            {studyUnit
              ? `${formatTextbookPageReference(studyUnit.pageLabel, 'source')} · ${studyUnit.itemCount} 条`
              : '内容尚未接入'}
          </Text>
        </View>
        {studyUnit ? (
          <Ionicons name="chevron-forward" size={18} color={TextbookEditorial.inkFaint} />
        ) : null}
      </TouchableOpacity>
    </View>
  )
}

export default function TextbookSectionScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { sectionId = '', from = '' } = useLocalSearchParams<{ sectionId?: string; from?: string }>()
  const fromMap = from === 'map'
  const sectionTitle = getRespiratorySectionTitle(sectionId)
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['textbookSection', sectionId, 'study-units'],
    queryFn: () => getSectionDetail(sectionId),
    enabled: !!sectionId,
    staleTime: 300_000,
  })

  const catalogChapter = useMemo(
    () => data ? findCatalogChapter(data.section.sectionTitle) : null,
    [data],
  )
  const studyUnits = useMemo(() => data ? buildChapterCatalogStudyUnits(data) : [], [data])
  const outlineEntries = useMemo<CatalogOutlineEntry[]>(() => {
    const catalogUnits = catalogChapter?.units ?? []
    return buildSectionOutlineEntries(catalogUnits, studyUnits)
  }, [catalogChapter, studyUnits])
  const hasFormalSectionOutline = outlineEntries.length > 0
  const displayEntries = hasFormalSectionOutline
    ? outlineEntries
    : studyUnits.map((studyUnit) => ({
      catalogUnit: { title: studyUnit.title },
      kind: 'leaf' as const,
      studyUnit,
      subsections: [],
    }))
  const totalItems = studyUnits.reduce((sum, unit) => sum + unit.itemCount, 0)
  const autoOpenedSingleUnit = useRef(false)

  useEffect(() => {
    if (!data || displayEntries.length !== 1 || autoOpenedSingleUnit.current) return
    const singleEntry = displayEntries[0]
    if (singleEntry.kind !== 'leaf' || !singleEntry.studyUnit) return
    autoOpenedSingleUnit.current = true
    router.replace(buildTextbookUnitRoute(sectionId, singleEntry.studyUnit.id, {
      from: from || undefined,
      via: 'catalog',
    }))
  }, [data, displayEntries, from, router, sectionId])

  const openUnit = (unit: StudyUnit) => {
    router.push(buildTextbookUnitRoute(sectionId, unit.id, {
      from: from || undefined,
      via: 'catalog',
    }))
  }

  const openSubsectionUnit = (unit: StudyUnit) => {
    router.push(buildTextbookUnitRoute(sectionId, unit.id, {
      from: from || undefined,
      via: 'section-subsection',
    }))
  }

  const goBack = () => {
    if (fromMap) {
      if (router.canGoBack()) {
        router.back()
      } else {
        router.replace(buildKnowledgeMapRoute())
      }
      return
    }
    if (router.canGoBack()) {
      router.back()
      return
    }
    router.replace(buildKnowledgeMapRoute())
  }

  return (
    <View style={styles.screen}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={[styles.topBar, { paddingTop: insets.top + Spacing.xs }]}>
        <TouchableOpacity
          style={styles.iconButton}
          onPress={goBack}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="返回上一页"
        >
          <Ionicons name="arrow-back" size={22} color={TextbookEditorial.ink} />
        </TouchableOpacity>
        <View style={styles.topCopy}>
          <Text style={styles.topEyebrow}>
            {hasFormalSectionOutline ? '章节目录' : '章节内容'}
          </Text>
          <Text style={styles.topTitle} numberOfLines={1}>
            {data?.section.sectionTitle || sectionTitle || '教材章节'}
          </Text>
          {data ? (
            <Text style={styles.topMeta} numberOfLines={1}>
              {data.partTitle} · {formatTextbookPageReference(data.section.pageRange, 'pdf')}
            </Text>
          ) : null}
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      {isLoading ? (
        <View style={styles.stateBlock}>
          <ActivityIndicator color={Colors.primary[700]} />
          <Text style={styles.stateText}>正在读取教材章节</Text>
        </View>
      ) : null}

      {error ? (
        <View style={styles.stateBlock}>
          <Ionicons name="alert-circle-outline" size={28} color={Colors.error} />
          <Text style={styles.stateTitle}>章节暂时不可用</Text>
          <Text style={styles.stateText}>请稍后重试，或检查本地教材视图。</Text>
          <TouchableOpacity style={styles.retryButton} onPress={() => refetch()} disabled={isFetching}>
            <Text style={styles.retryText}>{isFetching ? '重试中' : '重新读取'}</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {!isLoading && !error && !data ? (
        <View style={styles.stateBlock}>
          <Ionicons name="document-text-outline" size={30} color={Colors.neutral[300]} />
          <Text style={styles.stateTitle}>没有找到这个章节</Text>
          <Text style={styles.stateText}>当前本地预览只开放已导出的教材章节。</Text>
        </View>
      ) : null}

      {data && displayEntries.length === 1 ? (
        <View style={styles.stateBlock}>
          <ActivityIndicator color={TextbookEditorial.accent} />
          <Text style={styles.stateText}>正在打开本章内容</Text>
        </View>
      ) : null}

      {data && displayEntries.length !== 1 ? (
        <>
          <View style={styles.chapterIntro}>
            <Text style={styles.introMeta}>
              {hasFormalSectionOutline
                ? `${displayEntries.length} 节`
                : '独立章节'} · {totalItems} 条内容
            </Text>
          </View>

          <View style={styles.unitList}>
            {displayEntries.length > 0 ? displayEntries.map((entry, index) => (
              <View
                key={entry.catalogUnit.title}
                style={index < displayEntries.length - 1 && styles.unitDivider}
              >
                <UnitRow
                  entry={entry}
                  onPressUnit={entry.kind === 'leaf' ? openUnit : openSubsectionUnit}
                />
              </View>
            )) : (
              <Text style={styles.emptyText}>本章暂时没有可展示的教材内容。</Text>
            )}
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
  content: {
    paddingTop: Spacing.base,
    paddingBottom: Layout.screenPaddingBottom,
  },
  topBar: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Spacing.xs,
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
    fontSize: 26,
    lineHeight: 32,
    color: TextbookEditorial.ink,
    fontWeight: '600',
    fontFamily: TextbookEditorialFonts.reading,
  },
  topMeta: {
    ...Typography.labelMedium,
    color: TextbookEditorial.inkMuted,
    marginTop: 2,
    fontFamily: TextbookEditorialFonts.ui,
  },
  chapterIntro: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.md,
  },
  introMeta: {
    ...Typography.bodyMedium,
    color: TextbookEditorial.inkMuted,
    lineHeight: 21,
    fontFamily: TextbookEditorialFonts.ui,
  },
  unitList: {
    paddingHorizontal: Layout.screenPaddingX,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: TextbookEditorial.rule,
  },
  unitDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: TextbookEditorial.rule,
  },
  unitRow: {
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingVertical: Spacing.md,
  },
  unitCopy: {
    flex: 1,
  },
  unitTitle: {
    fontSize: 18,
    lineHeight: 25,
    color: TextbookEditorial.ink,
    fontWeight: '600',
    fontFamily: TextbookEditorialFonts.reading,
  },
  unitMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  unitBlock: {
    paddingLeft: Spacing.xs,
  },
  subsectionList: {
    marginLeft: Spacing.md,
    paddingLeft: Spacing.base,
    paddingBottom: Spacing.md,
    borderLeftWidth: 1,
    borderLeftColor: Colors.primary[200],
    gap: Spacing.xs,
  },
  unitGroupTitle: {
    fontSize: 13,
    lineHeight: 18,
    color: TextbookEditorial.inkMuted,
    fontWeight: '600',
    fontFamily: TextbookEditorialFonts.reading,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xs,
  },
  subsectionRow: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.xs,
  },
  subsectionDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: Colors.primary[500],
  },
  subsectionCopy: {
    flex: 1,
  },
  subsectionTitle: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    fontFamily: TextbookEditorialFonts.reading,
  },
  subsectionTitleMuted: {
    color: Colors.textTertiary,
  },
  subsectionMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  unitTitleMuted: {
    color: Colors.textTertiary,
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
    margin: Layout.screenPaddingX,
  },
  stateTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
    marginTop: Spacing.sm,
  },
  stateText: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
    lineHeight: 21,
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

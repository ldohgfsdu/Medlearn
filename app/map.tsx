import React, { useMemo, useState } from 'react'
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
import { useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useSearchNodes, useSubjectCatalog, useTreeBySubject } from '@/hooks/useKnowledge'
import {
  isChapterLeaf,
  isSectionLeaf,
  type KnowledgeChapter,
  type KnowledgePart,
  type KnowledgeSection,
  type KnowledgeSubsection,
} from '@/utils/knowledgeTree'
import { displayNodeTitle } from '@/utils/knowledgeCatalog'
import { BorderRadius, Colors, Shadows, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { resolveCatalogTarget, type KnowledgeNavigationNode } from '@/utils/routeBuilders'
import type { ChapterSection } from '@/hooks/useKnowledge'

export const options = { headerTitle: '知识地图' }

const TYPE_COLORS: Record<string, string> = {
  disease: Colors.error,
  concept: Colors.primary[500],
  mechanism: Colors.info,
  symptom: Colors.warning,
  treatment: Colors.success,
}

const SUBJECT_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  内科学: 'heart-outline',
  外科学: 'medkit-outline',
  生理学: 'pulse-outline',
  病理学: 'scan-outline',
  药理学: 'flask-outline',
  诊断学: 'search-outline',
  儿科学: 'happy-outline',
  妇产科学: 'female-outline',
  神经病学: 'git-network-outline',
  医学免疫学: 'shield-checkmark-outline',
}

const RESPIRATORY_PART = '第二篇 呼吸系统疾病'
const GOLDEN_DISEASES = new Set([
  '慢性阻塞性肺疾病',
  '支气管哮喘',
  '肺炎链球菌肺炎',
  '肺结核',
  '肺癌',
])

/** Convert ChapterSection[] (from useTreeBySubject) to KnowledgePart[] for the new render tree. */
function chapterSectionsToKnowledgeParts(sections: ChapterSection[]): KnowledgePart[] {
  return sections.map((section) => ({
    name: section.name,
    chapters: (section.chapters ?? []).map((chapter) => ({
      name: chapter.name,
      sections: [{
        name: chapter.name,
        catalogTitle: chapter.name,
        subsections: chapter.nodes.map((node) => ({
          name: node.title,
          nodeCount: 1,
          hasData: true,
          target: {
            content_class: 'confirmed_disease' as const,
            node_type: 'disease' as const,
            content_status: 'available' as const,
            disease_id: node.id,
          },
        })),
        nodeCount: chapter.nodes.length,
        hasData: chapter.nodes.length > 0,
        target: chapter.nodes[0]
          ? {
              content_class: 'confirmed_disease' as const,
              node_type: 'disease' as const,
              content_status: 'available' as const,
              disease_id: chapter.nodes[0].id,
            }
          : undefined,
      }],
      hasCatalogUnits: chapter.nodes.length > 0,
      hasData: chapter.nodes.length > 0,
      target: chapter.nodes[0]
        ? {
            content_class: 'confirmed_disease' as const,
            node_type: 'disease' as const,
            content_status: 'available' as const,
            disease_id: chapter.nodes[0].id,
          }
        : undefined,
    })),
  }))
}

type CatalogStatus = 'available' | 'overview' | 'in_progress'

function getCatalogStatus(
  target: KnowledgeNavigationNode | undefined,
  _hasData: boolean,
): CatalogStatus {
  if (target?.node_type === 'overview') return 'overview'
  if (target?.content_status === 'available') return 'available'
  return 'in_progress'
}

function CatalogStatusBadge({ status }: { status: CatalogStatus }) {
  const config = {
    available: { label: '可学习', icon: 'checkmark-circle' as const },
    overview: { label: '总览', icon: 'git-branch-outline' as const },
    in_progress: { label: '整理中', icon: 'time-outline' as const },
  }[status]

  return (
    <View style={[styles.statusBadge, styles[`statusBadge_${status}`]]}>
      <Ionicons
        name={config.icon}
        size={12}
        color={status === 'available'
          ? Colors.primary[700]
          : status === 'overview'
            ? Colors.info
            : Colors.textTertiary}
      />
      <Text style={[styles.statusBadgeText, styles[`statusBadgeText_${status}`]]}>
        {config.label}
      </Text>
    </View>
  )
}

function countPartNodes(part: KnowledgePart) {
  return part.chapters.reduce(
    (sum: number, chapter: KnowledgeChapter) => sum + chapter.sections.reduce((sectionSum: number, section: KnowledgeSection) => {
      const subsectionCount = section.subsections.reduce((subsectionSum: number, subsection: KnowledgeSubsection) => (
        subsectionSum + subsection.nodeCount
      ), 0)
      return sectionSum + subsectionCount
    }, 0),
    0,
  )
}

function chapterKey(partName: string, chapterName: string) {
  return `${partName}::${chapterName}`
}

function sectionKey(partName: string, chapterName: string, sectionCatalogTitle: string) {
  return `${partName}::${chapterName}::${sectionCatalogTitle}`
}

export default function KnowledgeMapScreen() {
  const [selectedSubject, setSelectedSubject] = useState<string | null>('内科学')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedParts, setExpandedParts] = useState<Set<string>>(new Set([RESPIRATORY_PART]))
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set())
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set())
  const router = useRouter()

  const { data: subjectCatalog, isLoading: loadingSubjects, refetch: refetchSubjects } = useSubjectCatalog()
  const { data: treeSections, isLoading: loadingTree } = useTreeBySubject(selectedSubject || '')
  const parts = useMemo(
    () => treeSections ? chapterSectionsToKnowledgeParts(treeSections) : undefined,
    [treeSections],
  )
  const { data: searchResults, isFetching: searching } = useSearchNodes(
    searchQuery,
    selectedSubject || undefined,
  )
  const hasSearch = searchQuery.trim().length >= 2
  const subjects = useMemo(() => subjectCatalog ?? [], [subjectCatalog])
  const totalCatalogNodes = useMemo(
    () => subjects.reduce((sum, entry) => sum + entry.nodeCount, 0),
    [subjects],
  )

  const respiratoryPart = useMemo(
    () => parts?.find((part) => part.name === RESPIRATORY_PART),
    [parts],
  )
  const goldenEntries = useMemo(() => {
    if (!respiratoryPart) return []
    const entries = respiratoryPart.chapters.flatMap((chapter) => (
      chapter.sections.flatMap((section) => (
        section.subsections
          .filter((subsection) => GOLDEN_DISEASES.has(subsection.name))
          .map((subsection) => ({
            name: subsection.name,
            target: subsection.target,
            hasData: subsection.hasData,
          }))
      ))
    ))
    return Array.from(
      new Map(entries.map((entry) => [entry.name, entry])).values(),
    )
  }, [respiratoryPart])

  const togglePart = (name: string) => {
    setExpandedParts((current) => {
      const next = new Set(current)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const toggleChapter = (partName: string, chapterName: string) => {
    const key = chapterKey(partName, chapterName)
    setExpandedChapters((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const toggleSection = (partName: string, chapterName: string, sectionCatalogTitle: string) => {
    const key = sectionKey(partName, chapterName, sectionCatalogTitle)
    setExpandedSections((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const selectSubject = (subject: string) => {
    setSelectedSubject(subject)
    setExpandedParts(new Set(subject === '内科学' ? [RESPIRATORY_PART] : []))
    setExpandedChapters(new Set())
    setExpandedSections(new Set())
    setSearchQuery('')
  }

  const clearSubject = () => {
    setSelectedSubject(null)
    setExpandedParts(new Set())
    setExpandedChapters(new Set())
    setExpandedSections(new Set())
    setSearchQuery('')
  }

  const focusRespiratoryCatalog = () => {
    setExpandedParts((current) => new Set(current).add(RESPIRATORY_PART))
  }

  const openResolvedTarget = (node: KnowledgeNavigationNode | undefined) => {
    if (!node) return
    const target = resolveCatalogTarget(node)
    if (target) router.push(target)
  }

  const chapterMeta = (chapter: KnowledgeChapter) => {
    const nodeCount = chapter.sections.reduce(
      (sum, section) => sum + section.nodeCount,
      0,
    )
    if (isChapterLeaf(chapter)) {
      return chapter.hasData ? `${nodeCount} 条` : '待入库'
    }
    return chapter.sections.length > 0
      ? chapter.hasData
        ? `${chapter.sections.length} 节 · ${nodeCount} 条`
        : `${chapter.sections.length} 节 · 待入库`
      : '待入库'
  }

  const sectionMeta = (section: KnowledgeSection) => {
    if (section.target?.node_type === 'overview') return '总览 · 分类导航'
    if (isSectionLeaf(section)) {
      return section.hasData ? `${section.nodeCount} 条` : '整理中'
    }
    return section.subsections.length > 0
      ? section.hasData
        ? `${section.subsections.length} 个小节 · ${section.nodeCount} 条`
        : `${section.subsections.length} 个小节 · 整理中`
      : '整理中'
  }

  const handleNodeClick = (node: KnowledgeNavigationNode) => {
    openResolvedTarget(node)
  }

  if (!selectedSubject) {
    return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.subjectContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.pageIntro}>
          <Text style={styles.pageIntroTitle}>从科目进入，把知识放回结构里</Text>
          <Text style={styles.pageIntroText}>
            按教材目录浏览知识点。先建立章节位置，再进入复述、测验与病例训练。
          </Text>
        </View>

        <View style={styles.sectionHeader}>
          <View>
            <Text style={styles.sectionTitle}>选择科目</Text>
            <Text style={styles.sectionMeta}>
              {loadingSubjects ? '整理中' : `${totalCatalogNodes} 个知识点`}
            </Text>
          </View>
          <Text style={styles.sectionCount}>{subjects?.length ?? 0} 科</Text>
        </View>

        {loadingSubjects ? (
          <View style={styles.loadingBlock}>
            <ActivityIndicator color={Colors.primary[700]} />
            <Text style={styles.loadingText}>正在整理科目目录</Text>
          </View>
        ) : subjects.length > 0 ? (
          <View style={styles.subjectList}>
            {subjects.map((entry, index) => (
              <TouchableOpacity
                key={entry.name}
                style={[
                  styles.subjectRow,
                  index < subjects.length - 1 && styles.rowDivider,
                ]}
                onPress={() => selectSubject(entry.name)}
                activeOpacity={0.65}
              >
                <View style={styles.subjectIcon}>
                  <Ionicons
                    name={SUBJECT_ICONS[entry.name] || 'book-outline'}
                    size={21}
                    color={Colors.primary[700]}
                  />
                </View>
                <View style={styles.subjectCopy}>
                  <Text style={styles.subjectName}>{entry.name}</Text>
                  <Text style={styles.subjectHint}>
                    {entry.nodeCount} 个知识点
                    {entry.textbooks[0] ? ` · ${entry.textbooks[0]}` : ''}
                  </Text>
                </View>
                <Ionicons name="arrow-forward" size={17} color={Colors.neutral[400]} />
              </TouchableOpacity>
            ))}
          </View>
        ) : (
          <View style={styles.emptyBlock}>
            <Text style={styles.emptyTitle}>暂时没有可浏览的科目</Text>
            <Text style={styles.emptyText}>教材数据导入后，科目目录会出现在这里。</Text>
            <TouchableOpacity style={styles.emptyAction} onPress={() => refetchSubjects()}>
              <Text style={styles.emptyActionText}>重新加载</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    )
  }

  return (
    <View style={styles.container}>
      <View style={styles.detailHeader}>
        <View style={styles.detailTitleRow}>
          <TouchableOpacity onPress={clearSubject} style={styles.backButton} activeOpacity={0.7}>
            <Ionicons name="arrow-back" size={18} color={Colors.ink} />
          </TouchableOpacity>
          <View style={styles.detailTitleCopy}>
            <Text style={styles.detailEyebrow}>教材目录</Text>
            <Text style={styles.detailTitle}>{selectedSubject}</Text>
            <Text style={styles.detailSubtitle}>第 10 版 · 按篇章浏览</Text>
          </View>
          <Pressable
            onPress={() => router.push('/search')}
            style={({ pressed }) => [styles.globalSearchButton, pressed && styles.pressed]}
            accessibilityRole="button"
            accessibilityLabel="打开知识搜索"
          >
            <Ionicons name="search" size={20} color={Colors.surface} />
          </Pressable>
        </View>

        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={18} color={Colors.textTertiary} />
          <TextInput
            style={styles.searchInput}
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="在内科学目录中搜索疾病"
            placeholderTextColor={Colors.textTertiary}
            returnKeyType="search"
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery('')} style={styles.clearSearch}>
              <Ionicons name="close" size={16} color={Colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.listContent} showsVerticalScrollIndicator={false}>
        {hasSearch ? (
          <View>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>搜索结果</Text>
              <Text style={styles.sectionCount}>{searching ? '…' : searchResults?.length ?? 0}</Text>
            </View>

            {searching ? (
              <View style={styles.loadingBlock}>
                <ActivityIndicator color={Colors.primary[700]} />
                <Text style={styles.loadingText}>正在查找知识点</Text>
              </View>
            ) : searchResults && searchResults.length > 0 ? (
              <View style={styles.resultList}>
                {searchResults.map((node, index) => (
                  <TouchableOpacity
                    key={node.id}
                    style={[
                      styles.resultRow,
                      index < searchResults.length - 1 && styles.rowDivider,
                    ]}
                    onPress={() => handleNodeClick(node)}
                    activeOpacity={0.65}
                  >
                    <View style={[
                      styles.typeDot,
                      { backgroundColor: TYPE_COLORS[node.type] || Colors.neutral[300] },
                    ]} />
                    <View style={styles.resultCopy}>
                      <Text style={styles.resultTitle}>
                        {displayNodeTitle(node.title, node.sub_chapter)}
                      </Text>
                      <Text style={styles.resultMeta} numberOfLines={1}>
                        {node.chapter || node.subject}
                        {node.sub_chapter ? ` · ${node.sub_chapter}` : ''}
                      </Text>
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={Colors.neutral[400]} />
                  </TouchableOpacity>
                ))}
              </View>
            ) : (
              <View style={styles.emptyBlock}>
                <Text style={styles.emptyTitle}>没有找到相关知识点</Text>
                <Text style={styles.emptyText}>试试更短、更接近教材标题的关键词。</Text>
              </View>
            )}
          </View>
        ) : loadingTree ? (
          <View style={styles.loadingBlock}>
            <ActivityIndicator color={Colors.primary[700]} />
            <Text style={styles.loadingText}>正在展开教材目录</Text>
          </View>
        ) : parts && parts.length > 0 ? (
          <>
            {respiratoryPart ? (
              <View style={styles.focusCard}>
                <View style={styles.focusCardTop}>
                  <View style={styles.focusIcon}>
                    <Ionicons name="fitness-outline" size={23} color="#EAF5F1" />
                  </View>
                  <View style={styles.focusCopy}>
                    <Text style={styles.focusEyebrow}>当前学习范围</Text>
                    <Text style={styles.focusTitle}>呼吸系统疾病</Text>
                    <Text style={styles.focusMeta}>
                      {respiratoryPart.chapters.length} 章 · 5 个黄金疾病已可查
                    </Text>
                  </View>
                  <Pressable
                    onPress={focusRespiratoryCatalog}
                    style={({ pressed }) => [styles.focusAction, pressed && styles.pressed]}
                  >
                    <Ionicons name="arrow-down" size={17} color={Colors.ink} />
                  </Pressable>
                </View>

                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.goldenDiseaseRow}
                >
                  {goldenEntries.map((entry) => (
                    <Pressable
                      key={entry.name}
                      onPress={() => openResolvedTarget(entry.target)}
                      style={({ pressed }) => [
                        styles.goldenDiseaseChip,
                        pressed && styles.goldenDiseaseChipPressed,
                      ]}
                    >
                      <View style={styles.goldenDiseaseDot} />
                      <Text style={styles.goldenDiseaseText}>{entry.name}</Text>
                    </Pressable>
                  ))}
                </ScrollView>
              </View>
            ) : null}

            <View style={styles.sectionHeader}>
              <View>
                <Text style={styles.sectionTitle}>完整目录</Text>
                <Text style={styles.sectionMeta}>可浏览全部篇章，未完善内容会明确标记</Text>
              </View>
              <View style={styles.catalogCountBadge}>
                <Text style={styles.catalogCountValue}>{parts.length}</Text>
                <Text style={styles.catalogCountLabel}>篇</Text>
              </View>
            </View>

            <View style={styles.chapterList}>
              {parts.map((part, partIndex) => {
                const isPartExpanded = expandedParts.has(part.name)
                const partNodeCount = countPartNodes(part)
                return (
                  <View
                    key={part.name}
                    style={styles.chapterGroup}
                  >
                    <TouchableOpacity
                      style={styles.chapterHeader}
                      onPress={() => togglePart(part.name)}
                      activeOpacity={0.65}
                    >
                      <View style={[
                        styles.partIndex,
                        part.name === RESPIRATORY_PART && styles.partIndexActive,
                      ]}>
                        <Text style={[
                          styles.partIndexText,
                          part.name === RESPIRATORY_PART && styles.partIndexTextActive,
                        ]}>
                          {String(partIndex + 1).padStart(2, '0')}
                        </Text>
                      </View>
                      <View style={styles.chapterCopy}>
                        <Text style={styles.chapterTitle}>{part.name}</Text>
                        <Text style={styles.chapterMeta}>
                          {part.chapters.length} 章
                          {partNodeCount > 0 ? ` · ${partNodeCount} 个知识节点` : ' · 目录已建立'}
                        </Text>
                      </View>
                      <View style={[styles.expandButton, isPartExpanded && styles.expandButtonActive]}>
                        <Ionicons
                          name={isPartExpanded ? 'chevron-up' : 'chevron-down'}
                          size={18}
                          color={isPartExpanded ? Colors.surface : Colors.primary[700]}
                        />
                      </View>
                    </TouchableOpacity>

                    {isPartExpanded && (
                      <View style={styles.partBody}>
                        {part.chapters.map((chapter) => {
                          const key = chapterKey(part.name, chapter.name)
                          const isChapterExpanded = expandedChapters.has(key)
                          const chapterIsLeaf = isChapterLeaf(chapter)
                          return (
                            <View key={key} style={styles.subChapter}>
                              <TouchableOpacity
                                style={styles.subChapterHeader}
                                onPress={() => {
                                  if (chapterIsLeaf) {
                                    openResolvedTarget(chapter.target)
                                    return
                                  }
                                  toggleChapter(part.name, chapter.name)
                                }}
                                activeOpacity={0.65}
                              >
                                <View style={[
                                  styles.chapterRailDot,
                                  chapter.hasData && styles.chapterRailDotActive,
                                ]} />
                                <View style={styles.subChapterCopy}>
                                  <Text style={styles.subChapterTitle}>{chapter.name}</Text>
                                  <Text style={styles.subChapterMeta}>{chapterMeta(chapter)}</Text>
                                </View>
                                {chapterIsLeaf ? (
                                  <CatalogStatusBadge
                                    status={getCatalogStatus(chapter.target, chapter.hasData)}
                                  />
                                ) : null}
                                <Ionicons
                                  name={chapterIsLeaf
                                    ? 'chevron-forward'
                                    : (isChapterExpanded ? 'chevron-up' : 'chevron-down')}
                                  size={16}
                                  color={chapterIsLeaf ? Colors.neutral[400] : Colors.textTertiary}
                                />
                              </TouchableOpacity>

                              {!chapterIsLeaf && isChapterExpanded && (
                                <View style={styles.topicList}>
                                  {chapter.sections.length > 0 ? (
                                    chapter.sections.map((section) => {
                                      const sectionExpandedKey = sectionKey(
                                        part.name,
                                        chapter.name,
                                        section.catalogTitle,
                                      )
                                      const isSectionExpanded = expandedSections.has(sectionExpandedKey)
                                      const sectionIsLeaf = isSectionLeaf(section)
                                      return (
                                        <View key={sectionExpandedKey} style={styles.sectionGroup}>
                                          <TouchableOpacity
                                            style={styles.sectionHeaderRow}
                                            onPress={() => {
                                              if (sectionIsLeaf) {
                                                openResolvedTarget(section.target)
                                                return
                                              }
                                              toggleSection(
                                                part.name,
                                                chapter.name,
                                                section.catalogTitle,
                                              )
                                            }}
                                            activeOpacity={0.65}
                                          >
                                            <CatalogStatusBadge
                                              status={getCatalogStatus(section.target, section.hasData)}
                                            />
                                            <View style={styles.topicCopy}>
                                              <Text style={styles.topicTitle}>{section.name}</Text>
                                              <Text style={styles.topicMeta}>{sectionMeta(section)}</Text>
                                            </View>
                                            <Ionicons
                                              name={sectionIsLeaf
                                                ? 'chevron-forward'
                                                : (isSectionExpanded ? 'chevron-up' : 'chevron-down')}
                                              size={15}
                                              color={sectionIsLeaf ? Colors.neutral[400] : Colors.textTertiary}
                                            />
                                          </TouchableOpacity>

                                          {!sectionIsLeaf && isSectionExpanded && (
                                            <View style={styles.subsectionList}>
                                              {section.subsections.length > 0 ? (
                                                section.subsections.map((subsection, subsectionIndex) => (
                                                  <TouchableOpacity
                                                    key={`${sectionExpandedKey}-${subsection.name}`}
                                                    style={[
                                                      styles.subsectionRow,
                                                      subsectionIndex < section.subsections.length - 1
                                                        && styles.subsectionRowDivider,
                                                    ]}
                                                    onPress={() => openResolvedTarget(subsection.target)}
                                                    activeOpacity={0.65}
                                                  >
                                                    <CatalogStatusBadge
                                                      status={getCatalogStatus(
                                                        subsection.target,
                                                        subsection.hasData,
                                                      )}
                                                    />
                                                    <View style={styles.topicCopy}>
                                                      <Text style={styles.subsectionTitle}>{subsection.name}</Text>
                                                      {subsection.hasData ? (
                                                        <Text style={styles.topicMeta}>
                                                          {subsection.nodeCount} 个知识节点
                                                        </Text>
                                                      ) : null}
                                                    </View>
                                                    <Ionicons
                                                      name="chevron-forward"
                                                      size={14}
                                                      color={Colors.neutral[400]}
                                                    />
                                                  </TouchableOpacity>
                                                ))
                                              ) : (
                                                <View style={styles.topicEmpty}>
                                                  <Text style={styles.topicEmptyText}>本节内容尚未入库</Text>
                                                </View>
                                              )}
                                            </View>
                                          )}
                                        </View>
                                      )
                                    })
                                  ) : (
                                    <View style={styles.topicEmpty}>
                                      <Text style={styles.topicEmptyText}>本章内容尚未入库</Text>
                                    </View>
                                  )}
                                </View>
                              )}
                            </View>
                          )
                        })}
                      </View>
                    )}
                  </View>
                )
              })}
            </View>
          </>
        ) : (
          <View style={styles.emptyBlock}>
            <Text style={styles.emptyTitle}>这个科目还没有目录</Text>
            <Text style={styles.emptyText}>完成教材解析后，章节结构会显示在这里。</Text>
            <TouchableOpacity style={styles.emptyAction} onPress={clearSubject}>
              <Text style={styles.emptyActionText}>选择其他科目</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  subjectContent: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Layout.screenPaddingBottom,
  },
  pageIntro: {
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.md,
  },
  pageIntroTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  pageIntroText: {
    fontSize: 15,
    lineHeight: 24,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
    maxWidth: 340,
  },
  sectionMeta: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
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
    borderRadius: Layout.cardRadius,
    paddingHorizontal: Layout.cardPadding,
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
  subjectIcon: {
    width: Layout.iconWrap,
    height: Layout.iconWrap,
    borderRadius: Layout.iconWrap / 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
    marginRight: Spacing.md,
  },
  subjectCopy: {
    flex: 1,
  },
  subjectName: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  subjectHint: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  detailHeader: {
    backgroundColor: Colors.background,
    paddingHorizontal: Layout.screenPaddingX,
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.base,
  },
  detailTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    marginRight: Spacing.md,
  },
  detailTitleCopy: {
    flex: 1,
  },
  detailEyebrow: {
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '800',
    letterSpacing: 1.4,
    color: Colors.primary[600],
  },
  detailTitle: {
    fontSize: 25,
    lineHeight: 30,
    fontWeight: '800',
    letterSpacing: -0.6,
    color: Colors.textPrimary,
  },
  detailSubtitle: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  globalSearchButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.ink,
  },
  pressed: {
    opacity: 0.72,
    transform: [{ scale: 0.98 }],
  },
  searchBox: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.full,
    paddingHorizontal: Spacing.base,
    ...Shadows.level1,
  },
  searchInput: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    paddingVertical: Spacing.md,
  },
  clearSearch: {
    width: 30,
    height: 30,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pathLink: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginTop: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.primary[50],
  },
  pathLinkCopy: {
    flex: 1,
  },
  pathLinkEyebrow: {
    fontSize: 8,
    lineHeight: 11,
    fontWeight: '800',
    letterSpacing: 1.2,
    color: Colors.primary[600],
    marginBottom: 2,
  },
  pathLinkTitle: {
    ...Typography.labelLarge,
    color: Colors.textPrimary,
  },
  listContent: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Layout.screenPaddingBottom,
    gap: Spacing.lg,
  },
  focusCard: {
    overflow: 'hidden',
    padding: Spacing.base,
    borderRadius: BorderRadius['2xl'],
    backgroundColor: Colors.ink,
    ...Shadows.level2,
  },
  focusCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  focusIcon: {
    width: 46,
    height: 46,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.md,
    backgroundColor: 'rgba(234, 245, 241, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(234, 245, 241, 0.16)',
  },
  focusCopy: {
    flex: 1,
  },
  focusEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '800',
    letterSpacing: 1.2,
    color: '#9BC9BB',
  },
  focusTitle: {
    fontSize: 19,
    lineHeight: 25,
    fontWeight: '800',
    color: '#FFFDF9',
    marginTop: 1,
  },
  focusMeta: {
    ...Typography.labelSmall,
    color: 'rgba(255, 253, 249, 0.58)',
    marginTop: 2,
  },
  focusAction: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#E7DCC9',
  },
  goldenDiseaseRow: {
    gap: Spacing.sm,
    paddingTop: Spacing.base,
  },
  goldenDiseaseChip: {
    height: 36,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: 'rgba(255, 253, 249, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255, 253, 249, 0.12)',
  },
  goldenDiseaseChipPressed: {
    backgroundColor: 'rgba(255, 253, 249, 0.16)',
  },
  goldenDiseaseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#79C6AD',
  },
  goldenDiseaseText: {
    ...Typography.labelMedium,
    color: '#FFFDF9',
    fontWeight: '700',
  },
  catalogCountBadge: {
    minWidth: 48,
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 16,
    backgroundColor: Colors.primary[50],
  },
  catalogCountValue: {
    fontSize: 17,
    lineHeight: 19,
    fontWeight: '800',
    color: Colors.primary[700],
    fontVariant: ['tabular-nums'],
  },
  catalogCountLabel: {
    fontSize: 9,
    lineHeight: 11,
    fontWeight: '700',
    color: Colors.primary[600],
  },
  loadingBlock: {
    minHeight: 180,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
  },
  loadingText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
  },
  emptyBlock: {
    minHeight: 180,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    justifyContent: 'flex-end',
  },
  emptyTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  emptyText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
  emptyAction: {
    alignSelf: 'flex-start',
    minHeight: 42,
    justifyContent: 'center',
    marginTop: Spacing.lg,
    paddingHorizontal: Spacing.xl,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.ink,
  },
  emptyActionText: {
    ...Typography.labelMedium,
    color: '#FFFDF9',
  },
  resultList: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
  },
  resultRow: {
    minHeight: Layout.listRowHeight,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  resultCopy: {
    flex: 1,
  },
  resultTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  resultMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  chapterList: {
    gap: Spacing.md,
  },
  chapterGroup: {
    overflow: 'hidden',
    paddingHorizontal: Spacing.base,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    backgroundColor: Colors.surface,
    ...Shadows.level1,
  },
  chapterHeader: {
    minHeight: 76,
    flexDirection: 'row',
    alignItems: 'center',
  },
  partIndex: {
    width: 38,
    height: 38,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.md,
    backgroundColor: Colors.neutral[100],
  },
  partIndexActive: {
    backgroundColor: Colors.primary[100],
  },
  partIndexText: {
    fontSize: 12,
    fontWeight: '800',
    color: Colors.textTertiary,
    fontVariant: ['tabular-nums'],
  },
  partIndexTextActive: {
    color: Colors.primary[700],
  },
  chapterCopy: {
    flex: 1,
    paddingRight: Spacing.md,
  },
  chapterTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  chapterMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 3,
  },
  expandButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
  },
  expandButtonActive: {
    backgroundColor: Colors.ink,
  },
  partBody: {
    paddingBottom: Spacing.base,
    paddingLeft: Spacing.sm,
    gap: 2,
    borderLeftWidth: 1,
    borderLeftColor: Colors.primary[100],
    marginLeft: 18,
  },
  subChapter: {
    position: 'relative',
  },
  subChapterHeader: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingLeft: Spacing.md,
    paddingRight: Spacing.sm,
    borderRadius: BorderRadius.lg,
  },
  chapterRailDot: {
    position: 'absolute',
    left: -13,
    width: 9,
    height: 9,
    borderRadius: 5,
    backgroundColor: Colors.neutral[200],
    borderWidth: 2,
    borderColor: Colors.surface,
  },
  chapterRailDotActive: {
    backgroundColor: Colors.primary[500],
  },
  subChapterCopy: {
    flex: 1,
    paddingRight: Spacing.sm,
  },
  subChapterTitle: {
    ...Typography.labelLarge,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  subChapterMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  topicList: {
    marginLeft: Spacing.md,
    marginBottom: Spacing.sm,
    paddingLeft: Spacing.sm,
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderLeftColor: Colors.border,
  },
  sectionGroup: {
    overflow: 'hidden',
    marginBottom: Spacing.xs,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.neutral[50],
  },
  sectionHeaderRow: {
    minHeight: 56,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
  },
  subsectionList: {
    paddingHorizontal: Spacing.sm,
    paddingBottom: Spacing.sm,
    backgroundColor: Colors.surface,
  },
  subsectionRow: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.sm,
  },
  subsectionRowDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  subsectionTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '500',
  },
  topicRow: {
    minHeight: Layout.listRowHeightCompact,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.sm,
  },
  topicRowDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  topicCopy: {
    flex: 1,
  },
  topicTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  topicMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  topicEmpty: {
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: Spacing.sm,
  },
  topicEmptyText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
  },
  typeDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    height: 24,
    paddingHorizontal: 7,
    borderRadius: BorderRadius.full,
  },
  statusBadge_available: {
    backgroundColor: Colors.primary[50],
  },
  statusBadge_overview: {
    backgroundColor: '#EAF3F6',
  },
  statusBadge_in_progress: {
    backgroundColor: Colors.neutral[100],
  },
  statusBadgeText: {
    fontSize: 10,
    lineHeight: 13,
    fontWeight: '700',
  },
  statusBadgeText_available: {
    color: Colors.primary[700],
  },
  statusBadgeText_overview: {
    color: Colors.info,
  },
  statusBadgeText_in_progress: {
    color: Colors.textTertiary,
  },
})

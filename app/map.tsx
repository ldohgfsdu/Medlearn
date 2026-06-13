import React, { useMemo, useState } from 'react'
import {
  ActivityIndicator,
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
import { displayNodeTitle } from '@/utils/knowledgeCatalog'
import { BorderRadius, Colors, Shadows, Spacing, Typography } from '@/constants/theme'

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

function countPartNodes(part: {
  nodes: { level?: number | null }[]
  chapters: { nodes: unknown[] }[]
}) {
  return part.nodes.filter((node) => node.level !== 2).length
    + part.chapters.reduce((sum, chapter) => sum + chapter.nodes.length, 0)
}

export default function KnowledgeMapScreen() {
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedParts, setExpandedParts] = useState<Set<string>>(new Set())
  const router = useRouter()

  const { data: subjectCatalog, isLoading: loadingSubjects, refetch: refetchSubjects } = useSubjectCatalog()
  const { data: parts, isLoading: loadingTree } = useTreeBySubject(selectedSubject || '')
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

  const effectiveExpandedParts = useMemo(() => {
    if (expandedParts.size > 0 || !parts?.length || hasSearch) {
      return expandedParts
    }
    return new Set([parts[0].name])
  }, [expandedParts, parts, hasSearch])

  const totalNodes = useMemo(
    () => parts?.reduce((sum, part) => sum + countPartNodes(part), 0) ?? 0,
    [parts],
  )

  const togglePart = (name: string) => {
    setExpandedParts((current) => {
      const next = new Set(current)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const selectSubject = (subject: string) => {
    setSelectedSubject(subject)
    setExpandedParts(new Set())
    setSearchQuery('')
  }

  const clearSubject = () => {
    setSelectedSubject(null)
    setExpandedParts(new Set())
    setSearchQuery('')
  }

  const handleNodeClick = (node: { id: string; title: string }) => {
    router.push({
      pathname: '/node/[id]',
      params: { id: node.id, title: node.title },
    })
  }

  if (!selectedSubject) {
    return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.subjectContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.catalogHero}>
          <Text style={styles.eyebrow}>KNOWLEDGE ATLAS</Text>
          <Text style={styles.catalogTitle}>从科目进入，{'\n'}把知识放回结构里</Text>
          <Text style={styles.catalogDescription}>
            按教材目录浏览知识点。先建立章节位置，再进入复述、测验与病例训练。
          </Text>
          <View style={styles.catalogMeta}>
            <Text style={styles.catalogMetaValue}>
              {loadingSubjects ? '—' : String(totalCatalogNodes).padStart(2, '0')}
            </Text>
            <Text style={styles.catalogMetaLabel}>可浏览知识点</Text>
          </View>
        </View>

        <View style={styles.sectionHeader}>
          <View>
            <Text style={styles.sectionEyebrow}>SUBJECT INDEX</Text>
            <Text style={styles.sectionTitle}>选择科目</Text>
          </View>
          <Text style={styles.sectionCount}>{String(subjects?.length ?? 0).padStart(2, '0')}</Text>
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
                <Text style={styles.subjectIndex}>{String(index + 1).padStart(2, '0')}</Text>
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
            <Text style={styles.emptyNumber}>00</Text>
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
            <Text style={styles.detailEyebrow}>CURRENT SUBJECT</Text>
            <Text style={styles.detailTitle}>{selectedSubject}</Text>
          </View>
          <View style={styles.nodeCount}>
            <Text style={styles.nodeCountValue}>{totalNodes}</Text>
            <Text style={styles.nodeCountLabel}>知识点</Text>
          </View>
        </View>

        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={18} color={Colors.textTertiary} />
          <TextInput
            style={styles.searchInput}
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="搜索两个字以上，如「心力衰竭」"
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
              <View>
                <Text style={styles.sectionEyebrow}>SEARCH RESULTS</Text>
                <Text style={styles.sectionTitle}>搜索结果</Text>
              </View>
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
                <Text style={styles.emptyNumber}>00</Text>
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
            <View style={styles.sectionHeader}>
              <View>
                <Text style={styles.sectionEyebrow}>TEXTBOOK OUTLINE</Text>
                <Text style={styles.sectionTitle}>教材目录</Text>
              </View>
              <Text style={styles.sectionCount}>{String(parts.length).padStart(2, '0')}</Text>
            </View>

            <View style={styles.chapterList}>
              {parts.map((part, partIndex) => {
                const isExpanded = effectiveExpandedParts.has(part.name)
                const partNodeCount = countPartNodes(part)
                return (
                  <View
                    key={part.name}
                    style={[
                      styles.chapterGroup,
                      partIndex < parts.length - 1 && styles.chapterGroupDivider,
                    ]}
                  >
                    <TouchableOpacity
                      style={styles.chapterHeader}
                      onPress={() => togglePart(part.name)}
                      activeOpacity={0.65}
                    >
                      <Text style={styles.chapterIndex}>
                        {String(partIndex + 1).padStart(2, '0')}
                      </Text>
                      <View style={styles.chapterCopy}>
                        <Text style={styles.chapterTitle}>{part.name}</Text>
                        <Text style={styles.chapterMeta}>{partNodeCount} 个知识点</Text>
                      </View>
                      <View style={[styles.expandButton, isExpanded && styles.expandButtonActive]}>
                        <Ionicons
                          name={isExpanded ? 'remove' : 'add'}
                          size={18}
                          color={isExpanded ? '#FFFDF9' : Colors.primary[700]}
                        />
                      </View>
                    </TouchableOpacity>

                    {isExpanded && (
                      <View style={styles.chapterBody}>
                        {part.nodes
                          .filter((node) => node.level !== 2)
                          .map((node, index) => (
                            <TouchableOpacity
                              key={node.id}
                              style={[
                                styles.nodeRow,
                                index === 0 && styles.nodeRowFirst,
                              ]}
                              onPress={() => handleNodeClick(node)}
                              activeOpacity={0.65}
                            >
                              <View style={[
                                styles.typeDot,
                                { backgroundColor: TYPE_COLORS[node.type] || Colors.neutral[300] },
                              ]} />
                              <Text style={styles.nodeText}>
                                {displayNodeTitle(node.title, node.sub_chapter)}
                              </Text>
                              <Ionicons name="chevron-forward" size={15} color={Colors.neutral[400]} />
                            </TouchableOpacity>
                          ))}

                        {part.chapters.map((chapter) => (
                          <View key={chapter.name} style={styles.subChapter}>
                            <View style={styles.subChapterHeader}>
                              <Text style={styles.subChapterTitle}>{chapter.name}</Text>
                              <Text style={styles.subChapterCount}>{chapter.nodes.length}</Text>
                            </View>
                            {chapter.nodes.map((node) => (
                              <TouchableOpacity
                                key={node.id}
                                style={styles.nodeRow}
                                onPress={() => handleNodeClick(node)}
                                activeOpacity={0.65}
                              >
                                <View style={[
                                  styles.typeDot,
                                  { backgroundColor: TYPE_COLORS[node.type] || Colors.neutral[300] },
                                ]} />
                                <Text style={styles.nodeText}>
                                  {displayNodeTitle(node.title, node.sub_chapter)}
                                </Text>
                                <Ionicons name="chevron-forward" size={15} color={Colors.neutral[400]} />
                              </TouchableOpacity>
                            ))}
                          </View>
                        ))}
                      </View>
                    )}
                  </View>
                )
              })}
            </View>
          </>
        ) : (
          <View style={styles.emptyBlock}>
            <Text style={styles.emptyNumber}>00</Text>
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
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing['4xl'],
  },
  catalogHero: {
    minHeight: 272,
    overflow: 'hidden',
    backgroundColor: Colors.ink,
    borderRadius: BorderRadius['2xl'],
    padding: Spacing.xl,
    marginBottom: Spacing['2xl'],
    ...Shadows.level2,
  },
  eyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '800',
    letterSpacing: 1.6,
    color: '#9DC8B9',
  },
  catalogTitle: {
    fontSize: 30,
    lineHeight: 38,
    fontWeight: '800',
    letterSpacing: -0.8,
    color: '#FFFDF9',
    marginTop: Spacing.md,
  },
  catalogDescription: {
    ...Typography.bodyMedium,
    lineHeight: 22,
    color: 'rgba(255, 253, 249, 0.64)',
    maxWidth: 320,
    marginTop: Spacing.md,
  },
  catalogMeta: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: Spacing.sm,
    marginTop: 'auto',
    paddingTop: Spacing.xl,
  },
  catalogMetaValue: {
    fontSize: 28,
    lineHeight: 32,
    fontWeight: '300',
    color: '#E7DCC9',
  },
  catalogMetaLabel: {
    ...Typography.labelSmall,
    color: 'rgba(255, 253, 249, 0.5)',
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
    minHeight: 82,
    flexDirection: 'row',
    alignItems: 'center',
  },
  rowDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  subjectIndex: {
    width: 30,
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textTertiary,
  },
  subjectIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
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
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.base,
  },
  detailTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.base,
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
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    letterSpacing: 1.2,
    color: Colors.textTertiary,
    marginBottom: 2,
  },
  detailTitle: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: '800',
    letterSpacing: -0.4,
    color: Colors.textPrimary,
  },
  nodeCount: {
    alignItems: 'flex-end',
  },
  nodeCountValue: {
    fontSize: 18,
    lineHeight: 22,
    fontWeight: '800',
    color: Colors.ink,
  },
  nodeCountLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  searchBox: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
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
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing['4xl'],
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
  emptyNumber: {
    fontSize: 42,
    lineHeight: 46,
    fontWeight: '300',
    color: Colors.neutral[200],
    marginBottom: Spacing.xl,
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
    minHeight: 70,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
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
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
  },
  chapterGroup: {
    overflow: 'hidden',
  },
  chapterGroupDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  chapterHeader: {
    minHeight: 82,
    flexDirection: 'row',
    alignItems: 'center',
  },
  chapterIndex: {
    width: 31,
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textTertiary,
  },
  chapterCopy: {
    flex: 1,
    paddingRight: Spacing.md,
  },
  chapterTitle: {
    ...Typography.titleSmall,
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
  chapterBody: {
    paddingLeft: 31,
    paddingBottom: Spacing.md,
  },
  subChapter: {
    marginTop: Spacing.sm,
  },
  subChapterHeader: {
    minHeight: 38,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.neutral[50],
    borderRadius: BorderRadius.md,
  },
  subChapterTitle: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
    fontWeight: '700',
  },
  subChapterCount: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  nodeRow: {
    minHeight: 54,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  nodeRowFirst: {
    borderTopWidth: 0,
  },
  typeDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  nodeText: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
  },
})

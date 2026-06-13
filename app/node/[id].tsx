import { useState } from 'react'
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native'
import { useLocalSearchParams } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useCausalChain, useKnowledgeNode, useRelatedChunks } from '@/hooks/useKnowledge'
import { displayNodeTitle, formatNodeType } from '@/utils/knowledgeCatalog'

import { Colors, Typography, Spacing, BorderRadius, Shadows } from '@/constants/theme'
import { parseContentPoints } from '@/utils/structuredContent'
import type { ContentPoint } from '@/utils/structuredContent'
import { buildKnowledgeOutline, extractDigestPoints } from '@/utils/knowledgeOutline'
import type { KnowledgeGroup, KnowledgeSection } from '@/utils/knowledgeOutline'


// 医学疾病的标准结构化子节点标题
const DISEASE_SECTIONS = [
  { title: '定义' },
  { title: '概述' },
  { title: '核心概念' },
  { title: '流行病学' },
  { title: '病因' },
  { title: '发病机制' },
  { title: '病因与发病机制' },
  { title: '病因与机制' },
  { title: '机制与解救' },
  { title: '吸收与代谢' },
  { title: '病理' },
  { title: '病理生理' },
  { title: '临床表现' },
  { title: '临床与诊断' },
  { title: '症状' },
  { title: '体征' },
  { title: '检查' },
  { title: '辅助检查' },
  { title: '实验室检查' },
  { title: '影像学检查' },
  { title: '诊断' },
  { title: '鉴别诊断' },
  { title: '诊断与鉴别' },
  { title: '诊断标准' },
  { title: '治疗' },
  { title: '治疗原则' },
  { title: '药物治疗' },
  { title: '手术治疗' },
  { title: '预后' },
  { title: '预防' },
  { title: '并发症' },
  { title: '分类' },
  { title: '分型' },
]

// 解析内容为结构化sections（兜底：从原始文本解析）
function parseStructuredContent(content: string): { title: string; content: string }[] {
  if (!content || content.length < 50) return []

  // 先把连续文本按标题标记拆分成行
  let text = content
  text = text.replace(/([。！？；\n])\s*【/g, '$1\n【')
  text = text.replace(/([。！？；\n])\s*([一二三四五六七八九十]+[、.．])/g, '$1\n$2')
  text = text.replace(/([。！？；\n])\s*([（(][一二三四五六七八九十\d]+[）)])/g, '$1\n$2')

  const lines = text.split('\n')
  const sections: { title: string; content: string }[] = []
  let currentTitle = ''
  let currentContent: string[] = []

  // 长标题优先匹配
  const sortedSections = [...DISEASE_SECTIONS].sort((a, b) => b.title.length - a.title.length)

  function tryMatchSection(line: string): { title: string; rest: string } | null {
    const s = line.trim()
    for (const sec of sortedSections) {
      const t = sec.title
      // 【标题】 格式（教材最常见）
      const bracketMatch = s.match(new RegExp(`^【${t}】\\s*[：:]*\\s*(.*)`))
      if (bracketMatch) {
        return { title: t, rest: bracketMatch[1].trim() }
      }
      // 标题： 单独一行
      if (new RegExp(`^${t}\\s*[：:]\\s*$`).test(s)) {
        return { title: t, rest: '' }
      }
      // 标题：内容
      const inlineMatch = s.match(new RegExp(`^${t}\\s*[：:]\\s*(.+)`))
      if (inlineMatch) {
        return { title: t, rest: inlineMatch[1].trim() }
      }
      // 一、标题
      const numMatch1 = s.match(new RegExp(`^[一二三四五六七八九十\\d]+[、.．]\\s*${t}\\s*[：:]*\\s*(.*)`))
      if (numMatch1) {
        return { title: t, rest: numMatch1[1].trim() }
      }
      // (一)标题
      const numMatch2 = s.match(new RegExp(`^[（(][一二三四五六七八九十\\d]+[）)]\\s*${t}\\s*[：:]*\\s*(.*)`))
      if (numMatch2) {
        return { title: t, rest: numMatch2[1].trim() }
      }
      // 1.标题
      const numMatch3 = s.match(new RegExp(`^\\d+\\.\\s*${t}\\s*[：:]*\\s*(.*)`))
      if (numMatch3) {
        return { title: t, rest: numMatch3[1].trim() }
      }
    }
    return null
  }

  for (const line of lines) {
    const s = line.trim()
    if (!s) continue

    const matched = tryMatchSection(s)
    if (matched) {
      if (currentTitle && currentContent.length > 0) {
        sections.push({ title: currentTitle, content: currentContent.join('\n') })
      }
      currentTitle = matched.title
      currentContent = matched.rest ? [matched.rest] : []
    } else {
      currentContent.push(s)
    }
  }

  if (currentTitle && currentContent.length > 0) {
    sections.push({ title: currentTitle, content: currentContent.join('\n') })
  }

  return sections
}

// 获取结构化sections：优先DB，其次解析
function getStructuredSections(node: any): { title: string; content: string }[] {
  // 1. 优先使用数据库中的 structured_sections
  if (node.structured_sections && Array.isArray(node.structured_sections) && node.structured_sections.length > 0) {
    return node.structured_sections.map((s: any) => ({
      title: s.title || '',
      content: s.content || '',
    })).filter((s: { title: string; content: string }) => s.title && s.content)
  }

  // 2. 兜底：从 content 文本解析
  const content: string = node.content || ''
  return parseStructuredContent(content)
}

type TabKey = 'knowledge' | 'reasoning'

const TABS: {
  key: TabKey
  label: string
  icon: React.ComponentProps<typeof Ionicons>['name']
}[] = [
  { key: 'knowledge', label: '知识', icon: 'book-outline' },
  { key: 'reasoning', label: '推导', icon: 'git-branch-outline' },
]

// 可折叠的section组件
function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
  expanded: controlledExpanded,
  onToggle,
}: {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
  expanded?: boolean
  onToggle?: () => void
}) {
  const [localExpanded, setLocalExpanded] = useState(defaultOpen)
  const expanded = controlledExpanded ?? localExpanded
  const toggle = onToggle ?? (() => setLocalExpanded(value => !value))

  return (
    <View style={styles.collapsibleCard}>
      <TouchableOpacity
        style={styles.collapsibleHeader}
        onPress={toggle}
        activeOpacity={0.7}
      >
        <View style={styles.collapsibleLeft}>
          <Text style={styles.collapsibleTitle}>{title}</Text>
        </View>
        <Ionicons
          name={expanded ? 'chevron-up' : 'chevron-down'}
          size={16}
          color={Colors.textTertiary}
        />
      </TouchableOpacity>
      {expanded && (
        <View style={styles.collapsibleBody}>
          {children}
        </View>
      )}
    </View>
  )
}

function StructuredSectionContent({ content }: { content: string }) {
  const points = parseContentPoints(content)

  if (points.length <= 1) {
    return <Text style={styles.sectionContent}>{content}</Text>
  }

  return (
    <View style={styles.contentPointList}>
      {points.map((point, index) => (
        <ContentPointItem
          key={`${point.marker}-${point.title}-${index}`}
          point={point}
          index={index}
          isLast={index === points.length - 1}
          defaultOpen={index === 0}
        />
      ))}
    </View>
  )
}

function getPointTitle(point: ContentPoint, index: number): string {
  if (point.title) return point.title
  const firstClause = point.body.split(/[：:，。；]/)[0]?.trim()
  if (firstClause) {
    return firstClause.length > 28 ? `${firstClause.slice(0, 28)}…` : firstClause
  }
  return `要点 ${String(index + 1).padStart(2, '0')}`
}

function ContentPointItem({
  point,
  index,
  isLast,
  defaultOpen,
}: {
  point: ContentPoint
  index: number
  isLast: boolean
  defaultOpen: boolean
}) {
  const [expanded, setExpanded] = useState(defaultOpen)
  const hasBody = !!point.body

  return (
    <View style={[
      styles.contentPoint,
      point.level === 0 && styles.contentPointLead,
      !isLast && styles.contentPointBorder,
    ]}>
      <TouchableOpacity
        style={styles.contentPointHeader}
        activeOpacity={hasBody ? 0.65 : 1}
        onPress={() => hasBody && setExpanded(value => !value)}
      >
        {point.marker ? (
          <View style={[
            styles.contentPointMarker,
            point.level >= 3 && styles.contentPointMarkerNested,
          ]}>
            <Text style={styles.contentPointMarkerText}>{point.marker.replace(/[【】]/g, '')}</Text>
          </View>
        ) : (
          <View style={styles.contentPointRule} />
        )}
        <Text style={styles.contentPointTitle}>{getPointTitle(point, index)}</Text>
        {hasBody && (
          <Ionicons
            name={expanded ? 'chevron-up' : 'chevron-down'}
            size={15}
            color={Colors.textTertiary}
          />
        )}
      </TouchableOpacity>
      {expanded && hasBody ? <Text style={styles.contentPointBody}>{point.body}</Text> : null}
    </View>
  )
}

function DigestSectionContent({ section }: { section: KnowledgeSection }) {
  const [showSource, setShowSource] = useState(false)

  return (
    <View>
      <View style={styles.digestList}>
        {section.digest.map((point, index) => (
          <View key={`${section.title}-${index}`} style={styles.digestRow}>
            <View style={styles.digestDot} />
            <Text style={styles.digestText}>{point}</Text>
          </View>
        ))}
      </View>

      <TouchableOpacity
        style={styles.sourceToggle}
        onPress={() => setShowSource(value => !value)}
        activeOpacity={0.7}
      >
        <Ionicons
          name={showSource ? 'eye-off-outline' : 'document-text-outline'}
          size={15}
          color={Colors.primary[600]}
        />
        <Text style={styles.sourceToggleText}>
          {showSource ? '收起教材原文' : '查看教材原文'}
        </Text>
      </TouchableOpacity>

      {showSource ? (
        <View style={styles.sourceDetail}>
          <StructuredSectionContent content={section.content} />
        </View>
      ) : null}
    </View>
  )
}

function OverviewCard({ points }: { points: string[] }) {
  if (points.length === 0) return null

  return (
    <View style={styles.overviewCard}>
      <View style={styles.overviewHeader}>
        <Text style={styles.overviewTitle}>先记这几条</Text>
      </View>
      {points.map((point, index) => (
        <View key={`${point}-${index}`} style={styles.overviewRow}>
          <Text style={styles.overviewNumber}>{index + 1}</Text>
          <Text style={styles.overviewText}>{point}</Text>
        </View>
      ))}
    </View>
  )
}

function TopicDirectory({
  groups,
  selectedIndex,
  onSelect,
}: {
  groups: KnowledgeGroup[]
  selectedIndex: number
  onSelect: (index: number) => void
}) {
  return (
    <View style={styles.directory}>
      <View style={styles.directoryHeader}>
        <View>
          <Text style={styles.directoryEyebrow}>CONTENTS</Text>
          <Text style={styles.directoryTitle}>子主题目录</Text>
        </View>
        <Text style={styles.directoryCount}>{String(groups.length).padStart(2, '0')}</Text>
      </View>
      <View style={styles.directoryList}>
        {groups.map((group, index) => {
          const selected = index === selectedIndex
          return (
            <TouchableOpacity
              key={group.title}
              style={[
                styles.directoryRow,
                index < groups.length - 1 && styles.directoryRowBorder,
                selected && styles.directoryRowSelected,
              ]}
              activeOpacity={0.65}
              onPress={() => onSelect(index)}
            >
              <Text style={[styles.directoryIndex, selected && styles.directoryIndexSelected]}>
                {String(index + 1).padStart(2, '0')}
              </Text>
              <View style={styles.directoryCopy}>
                <Text style={[styles.directoryItemTitle, selected && styles.directoryItemTitleSelected]}>
                  {group.title}
                </Text>
                <Text style={styles.directoryMeta} numberOfLines={1}>
                  {group.sections.map(section => section.title).join(' · ')}
                </Text>
              </View>
              <View style={[styles.directoryMark, selected && styles.directoryMarkSelected]}>
                <Ionicons
                  name={selected ? 'checkmark' : 'arrow-forward'}
                  size={15}
                  color={selected ? '#FFFDF9' : Colors.primary[700]}
                />
              </View>
            </TouchableOpacity>
          )
        })}
      </View>
    </View>
  )
}

function SectionDirectory({
  sections,
  selectedIndex,
  onSelect,
}: {
  sections: KnowledgeSection[]
  selectedIndex: number
  onSelect: (index: number) => void
}) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.sectionDirectory}
    >
      {sections.map((section, index) => {
        const selected = index === selectedIndex
        return (
          <TouchableOpacity
            key={`${section.title}-${index}`}
            style={[styles.sectionDirectoryItem, selected && styles.sectionDirectoryItemSelected]}
            activeOpacity={0.7}
            onPress={() => onSelect(index)}
          >
            <Text style={[styles.sectionDirectoryIndex, selected && styles.sectionDirectoryIndexSelected]}>
              {String(index + 1).padStart(2, '0')}
            </Text>
            <Text style={[styles.sectionDirectoryText, selected && styles.sectionDirectoryTextSelected]}>
              {section.title}
            </Text>
          </TouchableOpacity>
        )
      })}
    </ScrollView>
  )
}

function RelatedSourceMaterial({ chunks }: { chunks: any[] }) {
  if (!chunks || chunks.length === 0) return null

  return (
    <View style={styles.section}>
      <CollapsibleSection title="补充教材原文">
        {chunks.map((chunk: any, index: number) => (
          <View key={index} style={styles.chunkCard}>
            <Text style={styles.chunkText}>{chunk.content}</Text>
            {chunk.page_number ? (
              <Text style={styles.chunkPage}>第 {chunk.page_number} 页</Text>
            ) : null}
          </View>
        ))}
      </CollapsibleSection>
    </View>
  )
}

// 知识内容组件
function KnowledgeTab({
  node,
  relatedChunks,
}: {
  node: any
  relatedChunks: { content: string; page_number?: number | null }[]
}) {
  const content: string = node.content || ''
  const rawSections = getStructuredSections(node)
  const outline = buildKnowledgeOutline(content, rawSections)
  const storedKeyPoints = Array.isArray(node.key_points)
    ? node.key_points.filter((point: unknown): point is string => typeof point === 'string' && point.trim().length > 0)
    : []
  const overviewPoints = storedKeyPoints.length > 0
    ? extractDigestPoints(storedKeyPoints.join('。'), 5)
    : outline.overview
  const [selectedGroupIndex, setSelectedGroupIndex] = useState(0)
  const [selectedSectionIndex, setSelectedSectionIndex] = useState(0)

  const selectedGroup = outline.groups[selectedGroupIndex] || outline.groups[0]
  const selectedSections = selectedGroup?.sections || []

  const selectGroup = (index: number) => {
    setSelectedGroupIndex(index)
    setSelectedSectionIndex(0)
  }

  if (!content && outline.groups.length === 0 && relatedChunks.length === 0) {
    return (
      <View style={styles.emptyState}>
        <Ionicons name="book-outline" size={48} color={Colors.neutral[300]} />
        <Text style={styles.emptyTitle}>暂无详细内容</Text>
        <Text style={styles.emptySubtitle}>该知识点的教材内容正在整理中</Text>
      </View>
    )
  }

  return (
    <ScrollView style={styles.tabContent} showsVerticalScrollIndicator={false}>
      <View style={styles.section}>
        <OverviewCard points={overviewPoints} />
        {outline.grouped ? (
          <>
            <TopicDirectory
              groups={outline.groups}
              selectedIndex={selectedGroupIndex}
              onSelect={selectGroup}
            />
            <View style={styles.activeTopic}>
              <View style={styles.activeTopicHeader}>
                <View style={styles.activeTopicNumber}>
                  <Text style={styles.activeTopicNumberText}>
                    {String(selectedGroupIndex + 1).padStart(2, '0')}
                  </Text>
                </View>
                <View style={styles.activeTopicCopy}>
                  <Text style={styles.activeTopicEyebrow}>CURRENT TOPIC</Text>
                  <Text style={styles.activeTopicTitle}>{selectedGroup?.title}</Text>
                </View>
              </View>

              <SectionDirectory
                sections={selectedSections}
                selectedIndex={selectedSectionIndex}
                onSelect={setSelectedSectionIndex}
              />

              {selectedSections.map((section, index) => (
                <CollapsibleSection
                  key={`${selectedGroup?.title}-${section.title}`}
                  title={section.title}
                  expanded={index === selectedSectionIndex}
                  onToggle={() => setSelectedSectionIndex(index)}
                >
                  <DigestSectionContent section={section} />
                </CollapsibleSection>
              ))}

              <View style={styles.topicPager}>
                <TouchableOpacity
                  style={[styles.topicPagerButton, selectedGroupIndex === 0 && styles.topicPagerButtonDisabled]}
                  disabled={selectedGroupIndex === 0}
                  onPress={() => selectGroup(selectedGroupIndex - 1)}
                >
                  <Ionicons name="arrow-back" size={16} color={Colors.textSecondary} />
                  <Text style={styles.topicPagerText}>上一主题</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    styles.topicPagerButton,
                    styles.topicPagerButtonPrimary,
                    selectedGroupIndex === outline.groups.length - 1 && styles.topicPagerButtonDisabled,
                  ]}
                  disabled={selectedGroupIndex === outline.groups.length - 1}
                  onPress={() => selectGroup(selectedGroupIndex + 1)}
                >
                  <Text style={styles.topicPagerTextPrimary}>下一主题</Text>
                  <Ionicons name="arrow-forward" size={16} color="#FFFDF9" />
                </TouchableOpacity>
              </View>
            </View>
          </>
        ) : (
          <>
            <View style={styles.simpleDirectoryHeader}>
              <View>
                <Text style={styles.directoryEyebrow}>CONTENTS</Text>
                <Text style={styles.directoryTitle}>本页目录</Text>
              </View>
              <Text style={styles.directoryCount}>{String(selectedSections.length).padStart(2, '0')}</Text>
            </View>
            <SectionDirectory
              sections={selectedSections}
              selectedIndex={selectedSectionIndex}
              onSelect={setSelectedSectionIndex}
            />
            <View style={styles.simpleSectionList}>
              {selectedSections.map((section, index) => (
                <CollapsibleSection
                  key={section.title}
                  title={section.title}
                  expanded={index === selectedSectionIndex}
                  onToggle={() => setSelectedSectionIndex(index)}
                >
                  <DigestSectionContent section={section} />
                </CollapsibleSection>
              ))}
            </View>
          </>
        )}
      </View>

      <RelatedSourceMaterial chunks={relatedChunks} />

      {node.textbook ? (
        <View style={styles.sourceRow}>
          <Text style={styles.sourceText}>来源：{node.textbook}</Text>
        </View>
      ) : null}
      <View style={{ height: 40 }} />
    </ScrollView>
  )
}

// 推导内容组件
function ReasoningTab({ node, chain, loading }: { node: any; chain: any; loading: boolean }) {
  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.primary[500]} />
      </View>
    )
  }

  return (
    <ScrollView style={styles.tabContent} showsVerticalScrollIndicator={false}>
      {chain && chain.steps ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>推导链</Text>
          <Text style={styles.chainTitle}>{chain.title}</Text>
          {(chain.steps as any[]).map((step: any, i: number) => (
            <View key={i} style={styles.stepCard}>
              <View style={styles.stepNumber}>
                <Text style={styles.stepNumberText}>{i + 1}</Text>
              </View>
              <View style={styles.stepContent}>
                <Text style={styles.stepTitle}>{step.title || `步骤 ${i + 1}`}</Text>
                <Text style={styles.stepText}>{step.content || step}</Text>
              </View>
            </View>
          ))}
        </View>
      ) : node.causal_links && node.causal_links.length > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>因果关系</Text>
          {(node.causal_links as any[]).map((link: any, i: number) => (
            <View key={i} style={styles.causalCard}>
              <Text style={styles.causalFrom}>{link.from || link}</Text>
              <Ionicons name="arrow-forward" size={16} color={Colors.primary[500]} />
              <Text style={styles.causalTo}>{link.to || ''}</Text>
            </View>
          ))}
        </View>
      ) : (
        <View style={styles.emptyState}>
          <Ionicons name="link-outline" size={48} color={Colors.neutral[300]} />
          <Text style={styles.emptyTitle}>暂无推导链</Text>
          <Text style={styles.emptySubtitle}>该知识点的推导关系正在整理中</Text>
        </View>
      )}
      <View style={{ height: 40 }} />
    </ScrollView>
  )
}

export default function NodeDetailScreen() {
  const { id, title: titleParam } = useLocalSearchParams<{ id: string; title?: string }>()

  const { data: node, isLoading: loadingNode } = useKnowledgeNode(id || '')
  const { data: relatedChunks = [] } = useRelatedChunks(id || '')
  const { data: chain, isLoading: loadingChain } = useCausalChain(id || '')

  const [activeTab, setActiveTab] = useState<TabKey>('knowledge')

  if (loadingNode) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.primary[500]} />
      </View>
    )
  }

  if (!node) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>知识点不存在</Text>
      </View>
    )
  }

  const displayTitle = displayNodeTitle(node.title, node.sub_chapter) || titleParam || node.title
  const breadcrumb = [node.chapter, node.sub_chapter].filter(Boolean).join(' · ')

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerEyebrow}>KNOWLEDGE NOTE</Text>
        {breadcrumb ? <Text style={styles.headerBreadcrumb}>{breadcrumb}</Text> : null}
        <Text style={styles.nodeTitle}>{displayTitle}</Text>
        <View style={styles.metaRow}>
          {node.type && (
            <View style={styles.metaBadge}>
              <Text style={styles.metaText}>{formatNodeType(node.type)}</Text>
            </View>
          )}
          {node.difficulty && (
            <View style={styles.metaBadge}>
              <Text style={styles.metaText}>难度 {node.difficulty}/3</Text>
            </View>
          )}
        </View>
      </View>

      {/* Tab 栏 */}
      <View style={styles.tabBar}>
        {TABS.map((tab) => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, activeTab === tab.key && styles.tabActive]}
            onPress={() => setActiveTab(tab.key)}
          >
            <Ionicons
              name={tab.icon}
              size={17}
              color={activeTab === tab.key ? Colors.primary[700] : Colors.textTertiary}
            />
            <Text style={[styles.tabLabel, activeTab === tab.key && styles.tabLabelActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* 内容区 - 根据当前tab显示不同内容 */}
      {activeTab === 'knowledge' && (
        <KnowledgeTab key={node.id} node={node} relatedChunks={relatedChunks} />
      )}
      {activeTab === 'reasoning' && <ReasoningTab node={node} chain={chain} loading={loadingChain} />}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
  },
  errorText: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
  },
  // 顶部
  header: {
    backgroundColor: Colors.background,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  headerEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '800',
    letterSpacing: 1.7,
    color: Colors.primary[700],
    marginBottom: Spacing.sm,
  },
  headerBreadcrumb: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginBottom: Spacing.xs,
  },
  nodeTitle: {
    fontSize: 29,
    lineHeight: 37,
    fontWeight: '800',
    letterSpacing: -0.7,
    color: Colors.textPrimary,
    marginBottom: Spacing.md,
  },
  metaRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  metaBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  metaText: {
    ...Typography.labelSmall,
    color: Colors.textSecondary,
  },
  // Tab 栏
  tabBar: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
    gap: Spacing.xs,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: Colors.primary[500],
  },
  tabLabel: {
    ...Typography.labelMedium,
    color: Colors.textTertiary,
  },
  tabLabelActive: {
    color: Colors.primary[500],
    fontWeight: '600',
  },
  // Tab 内容
  tabContent: {
    flex: 1,
  },
  section: {
    padding: Spacing.lg,
  },
  sectionTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
    marginBottom: Spacing.lg,
  },
  // 可折叠section
  collapsibleCard: {
    backgroundColor: 'transparent',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  collapsibleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    minHeight: 52,
    paddingHorizontal: Spacing.xs,
    paddingVertical: Spacing.md,
  },
  collapsibleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  collapsibleTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
    flex: 1,
  },
  collapsibleBody: {
    paddingHorizontal: Spacing.xs,
    paddingBottom: Spacing.lg,
  },
  sectionContent: {
    fontSize: 15,
    lineHeight: 25,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  overviewCard: {
    backgroundColor: Colors.ink,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  overviewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  overviewTitle: {
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '800',
    letterSpacing: 1.4,
    color: '#D8EBE0',
  },
  overviewRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.sm,
    paddingVertical: Spacing.xs,
  },
  overviewNumber: {
    ...Typography.labelSmall,
    color: Colors.accent,
    fontWeight: '700',
    width: 18,
    height: 18,
    lineHeight: 18,
    textAlign: 'center',
  },
  overviewText: {
    fontSize: 15,
    lineHeight: 25,
    color: '#FFFDF9',
    flex: 1,
  },
  learningActions: {
    gap: Spacing.sm,
    marginBottom: Spacing.xl,
  },
  learningActionPrimary: {
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.ink,
  },
  learningActionSecondary: {
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  learningActionCopy: {
    flex: 1,
  },
  learningActionEyebrowPrimary: {
    fontSize: 8,
    lineHeight: 12,
    fontWeight: '800',
    letterSpacing: 1.3,
    color: '#9DC8B9',
    marginBottom: 2,
  },
  learningActionEyebrow: {
    fontSize: 8,
    lineHeight: 12,
    fontWeight: '800',
    letterSpacing: 1.3,
    color: Colors.textTertiary,
    marginBottom: 2,
  },
  learningActionTitlePrimary: {
    ...Typography.titleSmall,
    color: '#FFFDF9',
  },
  learningActionTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  directory: {
    marginBottom: Spacing.xl,
  },
  directoryHeader: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  directoryEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '800',
    letterSpacing: 1.6,
    color: Colors.primary[600],
    marginBottom: 3,
  },
  directoryTitle: {
    fontSize: 21,
    lineHeight: 28,
    fontWeight: '800',
    letterSpacing: -0.3,
    color: Colors.textPrimary,
  },
  directoryCount: {
    fontSize: 28,
    lineHeight: 32,
    fontWeight: '300',
    letterSpacing: -1,
    color: Colors.primary[300],
  },
  directoryList: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
  },
  directoryRow: {
    minHeight: 76,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  directoryRowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  directoryRowSelected: {
    backgroundColor: Colors.primary[50],
  },
  directoryIndex: {
    width: 30,
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '700',
    color: Colors.textTertiary,
  },
  directoryIndexSelected: {
    color: Colors.primary[700],
  },
  directoryCopy: {
    flex: 1,
  },
  directoryItemTitle: {
    fontSize: 15,
    lineHeight: 21,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  directoryItemTitleSelected: {
    color: Colors.primary[800],
  },
  directoryMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 4,
  },
  directoryMark: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
  },
  directoryMarkSelected: {
    backgroundColor: Colors.ink,
  },
  sectionDirectory: {
    gap: Spacing.sm,
    paddingBottom: Spacing.lg,
  },
  sectionDirectoryItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    minHeight: 38,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  sectionDirectoryItemSelected: {
    backgroundColor: Colors.ink,
    borderColor: Colors.ink,
  },
  sectionDirectoryIndex: {
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '800',
    color: Colors.primary[500],
  },
  sectionDirectoryIndexSelected: {
    color: Colors.accent,
  },
  sectionDirectoryText: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
  },
  sectionDirectoryTextSelected: {
    color: '#FFFDF9',
  },
  activeTopic: {
    marginBottom: Spacing.lg,
  },
  activeTopicHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  activeTopicNumber: {
    width: 48,
    height: 48,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[100],
  },
  activeTopicNumberText: {
    fontSize: 17,
    lineHeight: 22,
    fontWeight: '800',
    color: Colors.primary[700],
  },
  activeTopicCopy: {
    flex: 1,
  },
  activeTopicEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '800',
    letterSpacing: 1.5,
    color: Colors.textTertiary,
    marginBottom: 2,
  },
  activeTopicTitle: {
    fontSize: 20,
    lineHeight: 27,
    fontWeight: '800',
    letterSpacing: -0.25,
    color: Colors.textPrimary,
  },
  topicPager: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.lg,
  },
  topicPagerButton: {
    flex: 1,
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  topicPagerButtonDisabled: {
    opacity: 0.35,
  },
  topicPagerText: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
  },
  topicPagerButtonPrimary: {
    backgroundColor: Colors.ink,
    borderColor: Colors.ink,
  },
  topicPagerTextPrimary: {
    ...Typography.labelMedium,
    color: '#FFFDF9',
  },
  simpleDirectoryHeader: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  simpleSectionList: {
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
  },
  digestList: {
    paddingTop: Spacing.sm,
  },
  digestRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  digestDot: {
    width: 16,
    height: 2,
    borderRadius: 1,
    backgroundColor: Colors.accent,
    marginTop: 11,
  },
  digestText: {
    fontSize: 15,
    lineHeight: 25,
    color: Colors.textPrimary,
    flex: 1,
  },
  sourceToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: Spacing.xs,
    paddingVertical: Spacing.sm,
    marginTop: Spacing.xs,
  },
  sourceToggleText: {
    ...Typography.labelMedium,
    color: Colors.primary[600],
  },
  sourceDetail: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
    marginTop: Spacing.xs,
    paddingTop: Spacing.sm,
  },
  fallbackContentCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
  },
  contentPointList: {
    marginTop: Spacing.xs,
  },
  contentPoint: {
    paddingVertical: Spacing.md,
  },
  contentPointLead: {
    backgroundColor: Colors.primary[50],
    marginHorizontal: -Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.xs,
  },
  contentPointBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  contentPointHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  contentPointMarker: {
    minWidth: 30,
    height: 24,
    paddingHorizontal: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[100],
    alignItems: 'center',
    justifyContent: 'center',
  },
  contentPointMarkerNested: {
    backgroundColor: Colors.surfaceVariant,
  },
  contentPointMarkerText: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '700',
  },
  contentPointRule: {
    width: 18,
    height: 2,
    borderRadius: 1,
    backgroundColor: Colors.accent,
  },
  contentPointTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
    flex: 1,
  },
  contentPointBody: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    lineHeight: 23,
    paddingLeft: 38,
  },
  // 知识内容
  contentHeading: {
    ...Typography.titleSmall,
    color: Colors.primary[600],
    fontWeight: '600',
    marginTop: Spacing.md,
    marginBottom: Spacing.sm,
  },
  contentRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    paddingLeft: Spacing.xs,
    marginBottom: Spacing.sm,
  },
  contentBullet: {
    ...Typography.bodyMedium,
    color: Colors.primary[400],
    marginTop: 2,
  },
  contentText: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    flex: 1,
    lineHeight: 22,
  },
  pointCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
    ...Shadows.level1,
  },
  pointNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: Colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
  },
  pointNumberText: {
    ...Typography.labelSmall,
    color: '#fff',
    fontWeight: '600',
  },
  pointText: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    flex: 1,
    lineHeight: 22,
  },
  chunkCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
    borderLeftWidth: 3,
    borderLeftColor: Colors.primary[200],
  },
  chunkText: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    lineHeight: 20,
  },
  chunkPage: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
    textAlign: 'right',
  },
  sourceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.base,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  sourceText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
  },
  // 推导内容
  chainTitle: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    marginBottom: Spacing.lg,
  },
  stepCard: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  stepNumber: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepNumberText: {
    ...Typography.labelSmall,
    color: '#fff',
    fontWeight: '600',
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    ...Typography.labelMedium,
    color: Colors.textPrimary,
    marginBottom: 2,
  },
  stepText: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    lineHeight: 20,
  },
  causalCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
    gap: Spacing.sm,
    ...Shadows.level1,
  },
  causalFrom: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    flex: 1,
  },
  causalTo: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    flex: 1,
  },
  // 训练内容
  trainingHint: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    marginBottom: Spacing.lg,
    lineHeight: 22,
  },
  textInput: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.base,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 150,
    marginBottom: Spacing.lg,
  },
  submitBtn: {
    backgroundColor: Colors.primary[500],
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    alignItems: 'center',
    marginBottom: Spacing.xl,
  },
  submitBtnDisabled: {
    opacity: 0.6,
  },
  submitBtnText: {
    ...Typography.labelLarge,
    color: '#fff',
  },
  resultCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    borderRadius: BorderRadius.lg,
    ...Shadows.level1,
  },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'center',
    marginBottom: Spacing.md,
  },
  scoreValue: {
    ...Typography.displayMedium,
    color: Colors.primary[500],
  },
  scoreUnit: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
    marginLeft: Spacing.xs,
  },
  feedback: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    lineHeight: 22,
    marginBottom: Spacing.lg,
  },
  missingSection: {
    marginBottom: Spacing.md,
  },
  missingTitle: {
    ...Typography.labelMedium,
    color: Colors.error,
    marginBottom: Spacing.sm,
  },
  missingItem: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    marginBottom: 2,
  },
  referenceRow: {
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  referenceText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
  },
  revisionButton: {
    minHeight: 44,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: Spacing.lg,
  },
  revisionButtonText: {
    ...Typography.labelLarge,
    color: '#fff',
    fontWeight: '700',
  },
  // 通用
  emptyState: {
    alignItems: 'center',
    paddingVertical: Spacing['2xl'],
  },
  emptyTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
    marginTop: Spacing.md,
  },
  emptySubtitle: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
})

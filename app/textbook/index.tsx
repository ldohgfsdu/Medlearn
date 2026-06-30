import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, type Href, useRouter } from 'expo-router'
import { useQuery } from '@tanstack/react-query'
import { Colors, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { getTextbookTree, type TextbookSectionSummary } from '@/services/textbookService'

function groupByPart(sections: TextbookSectionSummary[]): [string, TextbookSectionSummary[]][] {
  const groups = new Map<string, TextbookSectionSummary[]>()
  for (const section of sections) {
    const key = section.partTitle || '未分篇'
    groups.set(key, [...(groups.get(key) ?? []), section])
  }
  return Array.from(groups.entries())
}

function SectionRow({ section, onPress }: { section: TextbookSectionSummary; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.sectionRow} activeOpacity={0.68} onPress={onPress}>
      <View style={styles.treeIndent}>
        <View style={styles.treeLine} />
      </View>
      <View style={styles.sectionCopy}>
        <Text style={styles.sectionTitle} numberOfLines={2}>{section.sectionTitle}</Text>
        <Text style={styles.sectionMeta}>
          {section.nodeCount} 条视图节点 · {section.pageRange} 页
        </Text>
        <View style={styles.badgeRow}>
          <Text style={styles.badge}>整理 {section.organizedCount}</Text>
          <Text style={styles.badge}>原文 {section.evidenceOnlyCount}</Text>
          {section.groupedCount > 0 ? <Text style={styles.badge}>聚合 {section.groupedCount}</Text> : null}
          {section.mergedCount > 0 ? <Text style={styles.badge}>合并 {section.mergedCount}</Text> : null}
        </View>
      </View>
      <Ionicons name="chevron-forward" size={18} color={Colors.neutral[400]} />
    </TouchableOpacity>
  )
}

export default function TextbookIndexScreen() {
  const router = useRouter()
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['textbookTree', 'internal-medicine-10', 'ev1-display-contract'],
    queryFn: getTextbookTree,
    staleTime: 300_000,
  })
  const partGroups = data ? groupByPart(data.sections) : []

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Stack.Screen options={{ title: '电子教材' }} />
      <View style={styles.pageIntro}>
        <Text style={styles.pageTitle}>电子教材</Text>
        <Text style={styles.pageSubtitle}>
          按教材篇章浏览 EV1 display contract。每条内容保留教材原文证据和页码。
        </Text>
      </View>

      {isLoading ? (
        <View style={styles.stateBlock}>
          <ActivityIndicator color={Colors.primary[700]} />
          <Text style={styles.stateText}>正在读取教材目录</Text>
        </View>
      ) : null}

      {error ? (
        <View style={styles.stateBlock}>
          <Ionicons name="alert-circle-outline" size={28} color={Colors.error} />
          <Text style={styles.stateTitle}>目录暂时不可用</Text>
          <Text style={styles.stateText}>请稍后重试，或检查本地 display contract fixture。</Text>
          <TouchableOpacity style={styles.retryButton} onPress={() => refetch()} disabled={isFetching}>
            <Text style={styles.retryText}>{isFetching ? '重试中' : '重新读取'}</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {data ? (
        <View style={styles.treePanel}>
          <View style={styles.bookRow}>
            <Ionicons name="book-outline" size={20} color={Colors.primary[700]} />
            <View style={styles.bookCopy}>
              <Text style={styles.bookTitle}>{data.textbookTitle}</Text>
              <Text style={styles.bookMeta}>{data.textbookId}</Text>
            </View>
          </View>

          {partGroups.map(([partTitle, sections]) => (
            <View key={partTitle} style={styles.partGroup}>
              <View style={styles.partRow}>
                <View style={styles.partIndent}>
                  <Ionicons name="chevron-down" size={16} color={Colors.textTertiary} />
                </View>
                <View style={styles.partCopy}>
                  <Text style={styles.partTitle}>{partTitle}</Text>
                  <Text style={styles.partMeta}>{sections.length} 章 · {sections[0]?.systemTitle}</Text>
                </View>
              </View>

              <View style={styles.sectionList}>
                {sections.map((section) => (
                  <SectionRow
                    key={section.id}
                    section={section}
                    onPress={() => router.push({
                      pathname: '/textbook/[sectionId]',
                      params: { sectionId: section.id },
                    } as unknown as Href)}
                  />
                ))}
              </View>
            </View>
          ))}
        </View>
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
  pageIntro: {
    paddingTop: Spacing.md,
    paddingBottom: Spacing.base,
  },
  pageTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  pageSubtitle: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  treePanel: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    overflow: 'hidden',
  },
  bookRow: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Layout.cardPadding,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  bookCopy: {
    flex: 1,
  },
  bookTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  bookMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  partGroup: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  partRow: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.primary[50],
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.primary[100],
  },
  partIndent: {
    width: 42,
    alignItems: 'center',
  },
  partCopy: {
    flex: 1,
    paddingRight: Layout.cardPadding,
  },
  partTitle: {
    ...Typography.titleSmall,
    color: Colors.primary[800],
  },
  partMeta: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    marginTop: 2,
  },
  sectionList: {
    paddingLeft: 0,
  },
  sectionRow: {
    minHeight: 74,
    flexDirection: 'row',
    alignItems: 'center',
    paddingRight: Layout.cardPadding,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  treeIndent: {
    width: 42,
    alignSelf: 'stretch',
    alignItems: 'center',
  },
  treeLine: {
    width: StyleSheet.hairlineWidth,
    flex: 1,
    backgroundColor: Colors.border,
  },
  sectionCopy: {
    flex: 1,
    paddingVertical: Spacing.sm,
  },
  sectionTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  sectionMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 3,
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
    marginTop: Spacing.xs,
  },
  badge: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    backgroundColor: Colors.primary[50],
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: 10,
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

import { useState } from 'react'
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
import { useSearchNodes } from '@/hooks/useKnowledge'
import { displayNodeTitle, formatNodeType } from '@/utils/knowledgeCatalog'
import { BorderRadius, Colors, Spacing, Typography } from '@/constants/theme'

const TYPE_COLORS: Record<string, string> = {
  disease: Colors.error,
  concept: Colors.primary[500],
  mechanism: Colors.info,
  symptom: Colors.warning,
  treatment: Colors.success,
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const router = useRouter()
  const trimmed = query.trim()
  const hasSearch = trimmed.length >= 2
  const { data: results, isFetching } = useSearchNodes(query)

  const handleNodePress = (node: { id: string; title: string }) => {
    router.push({
      pathname: '/node/[id]',
      params: { id: node.id, title: node.title },
    })
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>知识搜索</Text>
        <Text style={styles.subtitle}>输入两个字以上，按教材知识点检索</Text>
        <View style={styles.searchBox}>
          <Ionicons name="search-outline" size={18} color={Colors.textTertiary} />
          <TextInput
            style={styles.searchInput}
            value={query}
            onChangeText={setQuery}
            placeholder="如「心力衰竭」「肺炎」"
            placeholderTextColor={Colors.textTertiary}
            autoCapitalize="none"
            returnKeyType="search"
            autoFocus
          />
          {query.length > 0 && (
            <TouchableOpacity
              onPress={() => setQuery('')}
              style={styles.clearButton}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Ionicons name="close" size={16} color={Colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {!hasSearch ? (
          <View style={styles.hintBlock}>
            <Ionicons name="book-outline" size={28} color={Colors.primary[700]} />
            <Text style={styles.hintTitle}>从关键词进入知识点</Text>
            <Text style={styles.hintText}>
              搜索结果会跳转到与知识地图相同的详情页，保持阅读体验一致。
            </Text>
          </View>
        ) : isFetching ? (
          <View style={styles.loadingBlock}>
            <ActivityIndicator color={Colors.primary[700]} />
            <Text style={styles.loadingText}>正在查找知识点</Text>
          </View>
        ) : results && results.length > 0 ? (
          <View style={styles.resultList}>
            {results.map((node, index) => (
              <TouchableOpacity
                key={node.id}
                style={[styles.resultRow, index < results.length - 1 && styles.rowDivider]}
                onPress={() => handleNodePress(node)}
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
                    {formatNodeType(node.type)}
                    {node.chapter ? ` · ${node.chapter}` : ''}
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
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.base,
    paddingBottom: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  title: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  subtitle: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
  searchBox: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.background,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
    marginTop: Spacing.md,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    lineHeight: 22,
    color: Colors.textPrimary,
    paddingVertical: Spacing.md,
  },
  clearButton: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing['4xl'],
  },
  hintBlock: {
    minHeight: 200,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.xl,
  },
  hintTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
    marginTop: Spacing.sm,
  },
  hintText: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
    textAlign: 'center',
    lineHeight: 22,
  },
  loadingBlock: {
    minHeight: 180,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
  },
  loadingText: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
  },
  resultList: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.base,
  },
  resultRow: {
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  rowDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  typeDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  resultCopy: {
    flex: 1,
  },
  resultTitle: {
    fontSize: 15,
    lineHeight: 22,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  resultMeta: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  emptyBlock: {
    minHeight: 180,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    justifyContent: 'center',
  },
  emptyTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  emptyText: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
    marginTop: Spacing.xs,
  },
})
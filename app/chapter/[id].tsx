import { useState } from 'react'
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, useLocalSearchParams, useRouter } from 'expo-router'
import { useChapterKnowledge } from '@/hooks/useDiseaseDetail'
import { Colors, FontFamily, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'

function nodeText(node: {
  content?: string | null
  key_points?: string[] | null
  structured_sections?: { title?: string; content?: string }[] | null
}) {
  const sections = node.structured_sections?.filter((item) => item.content?.trim()) ?? []
  if (sections.length) {
    return sections
      .map((item) => item.title ? `${item.title}\n${item.content}` : item.content)
      .join('\n\n')
  }
  if (node.content?.trim()) return node.content.trim()
  return node.key_points?.join('\n') ?? ''
}

export default function ChapterKnowledgeScreen() {
  const { id = '' } = useLocalSearchParams<{ id?: string }>()
  const router = useRouter()
  const { data, isLoading } = useChapterKnowledge(id)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (isLoading) {
    return <View style={styles.center}><ActivityIndicator color={Colors.primary[700]} /></View>
  }

  if (!data) {
    return (
      <View style={styles.center}>
        <Text style={styles.title}>章节不存在或暂不可访问</Text>
        <TouchableOpacity onPress={() => router.back()}><Text style={styles.link}>返回</Text></TouchableOpacity>
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <TouchableOpacity style={styles.back} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={18} color={Colors.textSecondary} />
          <Text style={styles.backText}>返回</Text>
        </TouchableOpacity>
        <Text style={styles.path}>{data.section.catalog_path}</Text>
        <Text style={styles.title}>{data.section.display_title}</Text>
        <Text style={styles.subtitle}>本页仅承接教材中的合法非疾病知识。</Text>
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        {data.nodes.length ? data.nodes.map((node) => {
          const expanded = expandedId === node.id
          const label = node.display_title || node.raw_aspect || node.title
          return (
            <View key={node.id} style={styles.card}>
              <TouchableOpacity style={styles.cardHeader} onPress={() => setExpandedId(expanded ? null : node.id)}>
                <Text style={styles.cardTitle}>{label}</Text>
                <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={18} color={Colors.textTertiary} />
              </TouchableOpacity>
              {expanded ? <Text style={styles.body}>{nodeText(node)}</Text> : null}
            </View>
          )
        }) : (
          <Text style={styles.empty}>本章节暂无可展示的非疾病知识。</Text>
        )}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl, backgroundColor: Colors.background },
  header: { paddingHorizontal: Layout.screenPaddingX, paddingVertical: Spacing.md, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border },
  back: { flexDirection: 'row', alignItems: 'center', minHeight: 44, marginBottom: Spacing.sm },
  backText: { ...Typography.labelMedium, color: Colors.textSecondary },
  path: { ...Typography.labelSmall, color: Colors.textTertiary },
  title: { ...Typography.titleLarge, fontFamily: FontFamily.serif, color: Colors.textPrimary, marginTop: Spacing.xs },
  subtitle: { ...Typography.bodyMedium, color: Colors.textSecondary, lineHeight: 21, marginTop: Spacing.xs },
  content: { padding: Layout.screenPaddingX, paddingBottom: Layout.screenPaddingBottom },
  card: { backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, borderRadius: Layout.cardRadius, padding: Layout.cardPadding, marginBottom: Spacing.sm },
  cardHeader: { minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  cardTitle: { ...Typography.titleSmall, fontFamily: FontFamily.serif, color: Colors.textPrimary, flex: 1 },
  body: { ...Typography.bodyMedium, color: Colors.textPrimary, lineHeight: 24, marginTop: Spacing.sm },
  empty: { ...Typography.bodyMedium, color: Colors.textTertiary, textAlign: 'center', marginTop: Spacing.xl },
  link: { ...Typography.labelLarge, color: Colors.primary[700], marginTop: Spacing.md },
})

import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, useLocalSearchParams, useRouter } from 'expo-router'
import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import { buildDiseaseRoute } from '@/utils/routeBuilders'
import { Colors, FontFamily, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'

const OVERVIEWS = {
  pneumonia: {
    title: '肺炎',
    path: '内科学 → 呼吸系统疾病 → 肺部感染性疾病',
    children: [
      '肺炎链球菌肺炎',
      '葡萄球菌肺炎',
      '肺炎克雷伯杆菌肺炎',
      '肺炎支原体肺炎',
      '病毒性肺炎',
    ],
  },
} as const

export default function KnowledgeOverviewScreen() {
  const { slug = '' } = useLocalSearchParams<{ slug?: string }>()
  const router = useRouter()
  const overview = OVERVIEWS[slug as keyof typeof OVERVIEWS]
  const { data, isLoading } = useQuery({
    queryKey: ['knowledgeOverview', slug],
    queryFn: async () => {
      if (!overview) return []
      const { data: entities, error } = await supabase
        .from('disease_entities')
        .select('disease_id, canonical_disease_name, content_status')
        .in('canonical_disease_name', [...overview.children])
        .eq('resolution_status', 'confirmed')
        .eq('node_type', 'disease')
      if (error) throw error
      return entities ?? []
    },
    enabled: !!overview,
  })

  if (!overview) {
    return (
      <View style={styles.center}>
        <Text style={styles.title}>总览节点不存在</Text>
        <TouchableOpacity onPress={() => router.back()}><Text style={styles.link}>返回</Text></TouchableOpacity>
      </View>
    )
  }

  const entitiesByName = new Map(data?.map((entity) => [entity.canonical_disease_name, entity]))

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <TouchableOpacity style={styles.back} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={18} color={Colors.textSecondary} />
          <Text style={styles.backText}>返回</Text>
        </TouchableOpacity>
        <Text style={styles.path}>{overview.path}</Text>
        <Text style={styles.title}>{overview.title}</Text>
        <Text style={styles.subtitle}>本页只提供教材分类与子疾病导航，不展示疾病正文。</Text>
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.sectionTitle}>相关疾病</Text>
        {isLoading ? <ActivityIndicator color={Colors.primary[700]} /> : overview.children.map((name) => {
          const entity = entitiesByName.get(name)
          const available = entity?.content_status === 'available'
          return (
            <TouchableOpacity
              key={name}
              style={styles.row}
              onPress={() => entity?.disease_id && router.push(buildDiseaseRoute(entity.disease_id))}
              disabled={!entity?.disease_id}
            >
              <View style={styles.rowCopy}>
                <Text style={styles.rowTitle}>{name}</Text>
                <Text style={styles.rowMeta}>{available ? '可查看完整疾病页' : '整理中'}</Text>
              </View>
              {entity?.disease_id ? <Ionicons name="chevron-forward" size={16} color={Colors.neutral[400]} /> : null}
            </TouchableOpacity>
          )
        })}
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
  sectionTitle: { ...Typography.titleMedium, fontFamily: FontFamily.serif, color: Colors.textPrimary, marginBottom: Spacing.md },
  row: { minHeight: 64, flexDirection: 'row', alignItems: 'center', paddingVertical: Spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border },
  rowCopy: { flex: 1 },
  rowTitle: { ...Typography.titleSmall, fontFamily: FontFamily.serif, color: Colors.textPrimary },
  rowMeta: { ...Typography.bodyMedium, color: Colors.textTertiary, lineHeight: 21, marginTop: 2 },
  link: { ...Typography.labelLarge, color: Colors.primary[700], marginTop: Spacing.md },
})

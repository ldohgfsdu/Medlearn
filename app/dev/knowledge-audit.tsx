import { Redirect } from 'expo-router'
import { ScrollView, StyleSheet, Text, View } from 'react-native'
import report from '@/reports/entity-resolution-audit.json'
import { Colors, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'

interface AuditCandidate {
  candidate_id: string
  candidate_name: string
  content_class: string
  confidence: number
  reason: string
}

export default function KnowledgeAuditScreen() {
  if (!__DEV__) return <Redirect href="/(tabs)" />
  const candidates = report.candidates as AuditCandidate[]

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>知识实体解析审计</Text>
      <Text style={styles.meta}>生成时间：{report.generated_at ?? '尚未运行回填脚本'}</Text>
      <View style={styles.summary}>
        {Object.entries(report.summary).map(([key, value]) => (
          <View key={key} style={styles.summaryRow}>
            <Text style={styles.summaryKey}>{key}</Text>
            <Text style={styles.summaryValue}>{value}</Text>
          </View>
        ))}
      </View>
      {candidates.map((candidate) => (
        <View key={candidate.candidate_id} style={styles.card}>
          <Text style={styles.cardTitle}>{candidate.candidate_name}</Text>
          <Text style={styles.cardText}>{candidate.content_class} · {candidate.confidence}</Text>
          <Text style={styles.cardText}>{candidate.reason}</Text>
        </View>
      ))}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Layout.screenPaddingX, paddingBottom: Layout.screenPaddingBottom },
  title: { ...Typography.titleLarge, color: Colors.textPrimary },
  meta: { ...Typography.bodySmall, color: Colors.textTertiary, marginTop: Spacing.xs },
  summary: { marginVertical: Spacing.lg },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: Spacing.xs },
  summaryKey: { ...Typography.bodyMedium, color: Colors.textSecondary },
  summaryValue: { ...Typography.labelLarge, color: Colors.textPrimary },
  card: { backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, borderRadius: Layout.cardRadius, padding: Layout.cardPadding, marginBottom: Spacing.sm },
  cardTitle: { ...Typography.titleSmall, color: Colors.textPrimary },
  cardText: { ...Typography.bodySmall, color: Colors.textSecondary, marginTop: Spacing.xs },
})

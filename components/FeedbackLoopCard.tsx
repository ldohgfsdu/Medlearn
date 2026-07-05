import { View, Text, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Colors, Typography, Spacing, BorderRadius } from '@/constants/theme'

interface FeedbackLoopCardProps {
  eyebrow?: string
  title: string
  summary: string
  action: string
}

export function FeedbackLoopCard({
  eyebrow,
  title,
  summary,
  action,
}: FeedbackLoopCardProps) {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.icon}>
          <Ionicons name="refresh-outline" size={18} color={Colors.primary[700]} />
        </View>
        {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
      </View>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.summary}>{summary}</Text>
      <View style={styles.actionRow}>
        <Text style={styles.actionLabel}>下一步</Text>
        <Text style={styles.action}>{action}</Text>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.primary[50],
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.primary[200],
    padding: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  icon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surface,
  },
  eyebrow: {
    ...Typography.labelSmall,
    fontWeight: '600',
    color: Colors.primary[700],
  },
  title: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
    marginBottom: Spacing.xs,
  },
  summary: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    lineHeight: 22,
  },
  actionRow: {
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.primary[200],
  },
  actionLabel: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '600',
    marginBottom: 3,
  },
  action: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
    lineHeight: 21,
  },
})

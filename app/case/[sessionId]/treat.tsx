import { useState } from 'react'

export const options = { headerTitle: '治疗方案' }
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native'
import { useLocalSearchParams, useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { submitCaseForScoring } from '@/services/case-submission'
import { Colors, Typography, Spacing, BorderRadius } from '@/constants/theme'

export default function TreatScreen() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>()
  const { user } = useAuth()

  const [treatments, setTreatments] = useState<string[]>(['', '', ''])
  const [loading, setLoading] = useState(false)

  const updateTreatment = (index: number, value: string) => {
    const updated = [...treatments]
    updated[index] = value
    setTreatments(updated)
  }

  const addTreatment = () => {
    if (treatments.length < 10) {
      setTreatments([...treatments, ''])
    }
  }

  const removeTreatment = (index: number) => {
    setTreatments(treatments.filter((_, i) => i !== index))
  }

  const handleSubmit = async () => {
    const validTreatments = treatments.filter((t) => t.trim())
    if (validTreatments.length === 0) {
      Alert.alert('提示', '请至少输入一项治疗措施')
      return
    }
    if (!user || !sessionId) return

    setLoading(true)
    try {
      await submitCaseForScoring(
        sessionId,
        validTreatments.map((item) => item.trim()),
      )

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['caseSession', sessionId] }),
        queryClient.invalidateQueries({ queryKey: ['homeStats'] }),
        queryClient.invalidateQueries({ queryKey: ['recentSessions'] }),
        queryClient.invalidateQueries({ queryKey: ['profileStats'] }),
        queryClient.invalidateQueries({ queryKey: ['analyticsStats'] }),
      ])

      router.push(`/case/${sessionId}/score`)
    } catch {
      Alert.alert('错误', '提交失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.pageIntro}>
        <Text style={styles.pageIntroTitle}>把诊断转化为处理方案</Text>
        <Text style={styles.pageIntroText}>按优先级写下治疗措施。先处理危险问题，再补充病因治疗与支持方案。</Text>
      </View>

      <View style={styles.sectionHeading}>
        <Text style={styles.sectionTitle}>治疗措施</Text>
        <Text style={styles.sectionMeta}>{treatments.length}/10</Text>
      </View>

      {treatments.map((treatment, i) => (
        <View key={i} style={styles.treatmentRow}>
          <Text style={styles.treatmentNumber}>{String(i + 1).padStart(2, '0')}</Text>
          <TextInput
            style={styles.treatmentInput}
            value={treatment}
            onChangeText={(v) => updateTreatment(i, v)}
            placeholder="治疗措施..."
            placeholderTextColor={Colors.textTertiary}
          />
          {treatments.length > 1 && (
            <TouchableOpacity style={styles.removeBtn} onPress={() => removeTreatment(i)}>
              <Ionicons name="close" size={17} color={Colors.error} />
            </TouchableOpacity>
          )}
        </View>
      ))}

      {treatments.length < 10 && (
        <TouchableOpacity style={styles.addButton} onPress={addTreatment}>
          <Ionicons name="add" size={17} color={Colors.primary[700]} />
          <Text style={styles.addButtonText}>添加治疗措施</Text>
        </TouchableOpacity>
      )}

      <TouchableOpacity
        style={[styles.submitButton, loading && styles.submitButtonDisabled]}
        onPress={handleSubmit}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <>
            <Text style={styles.submitButtonText}>提交治疗方案</Text>
            <Ionicons name="arrow-forward" size={18} color="#FFFDF9" />
          </>
        )}
      </TouchableOpacity>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing['4xl'],
  },
  pageIntro: {
    paddingBottom: Spacing.lg,
    marginBottom: Spacing.md,
  },
  pageIntroTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  pageIntroText: {
    ...Typography.bodyMedium,
    lineHeight: 24,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  sectionHeading: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    flex: 1,
    ...Typography.titleMedium,
    color: Colors.textPrimary,
  },
  sectionMeta: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  treatmentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  treatmentNumber: {
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textTertiary,
    width: 24,
  },
  treatmentInput: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 48,
  },
  removeBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FAF0ED',
  },
  addButton: {
    minHeight: 44,
    flexDirection: 'row',
    gap: Spacing.xs,
    justifyContent: 'center',
    padding: Spacing.sm,
    alignItems: 'center',
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  addButtonText: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
  },
  submitButton: {
    flexDirection: 'row',
    gap: Spacing.sm,
    backgroundColor: Colors.ink,
    padding: Spacing.base,
    borderRadius: BorderRadius.full,
    alignItems: 'center',
    marginTop: Spacing.xl,
    minHeight: 48,
    justifyContent: 'center',
  },
  submitButtonDisabled: {
    opacity: 0.6,
  },
  submitButtonText: {
    ...Typography.labelLarge,
    color: '#FFFDF9',
    fontWeight: '700',
  },
})

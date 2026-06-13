import { useState } from 'react'
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
import { useAuth } from '@/hooks/useAuth'
import { supabase } from '@/lib/supabase'
import { trackCaseEvent } from '@/services/analytics'
import type { ConfidenceLevel } from '@/utils/learningChallenge'
import { Colors, Typography, Spacing, BorderRadius } from '@/constants/theme'

export default function DiagnoseScreen() {
  const router = useRouter()
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>()
  const { user } = useAuth()

  const [primaryDiagnosis, setPrimaryDiagnosis] = useState('')
  const [differentials, setDifferentials] = useState<{ diagnosis: string; reasoning: string }[]>([
    { diagnosis: '', reasoning: '' },
  ])
  const [evidence, setEvidence] = useState<string[]>(['', '', ''])
  const [confidence, setConfidence] = useState<ConfidenceLevel>(2)
  const [uncertainty, setUncertainty] = useState('')
  const [loading, setLoading] = useState(false)

  const addDifferential = () => {
    if (differentials.length < 5) {
      setDifferentials([...differentials, { diagnosis: '', reasoning: '' }])
    }
  }

  const updateDifferential = (index: number, field: 'diagnosis' | 'reasoning', value: string) => {
    const updated = [...differentials]
    updated[index][field] = value
    setDifferentials(updated)
  }

  const removeDifferential = (index: number) => {
    setDifferentials(differentials.filter((_, i) => i !== index))
  }

  const updateEvidence = (index: number, value: string) => {
    const updated = [...evidence]
    updated[index] = value
    setEvidence(updated)
  }

  const addEvidence = () => {
    if (evidence.length < 8) {
      setEvidence([...evidence, ''])
    }
  }

  const handleSubmit = async () => {
    if (!primaryDiagnosis.trim()) {
      Alert.alert('提示', '请输入主要诊断')
      return
    }
    if (!user || !sessionId) return

    setLoading(true)
    try {
      const submission = {
        primaryDiagnosis: primaryDiagnosis.trim(),
        differentials: differentials
          .filter((item) => item.diagnosis.trim())
          .map((item) => ({
            diagnosis: item.diagnosis.trim(),
            reasoning: item.reasoning.trim(),
          })),
        evidence: evidence.map((item) => item.trim()).filter(Boolean),
        confidence,
        uncertainty: uncertainty.trim(),
      }
      const { data: updatedSession, error: updateError } = await supabase
        .from('case_sessions')
        .update({
          current_phase: 'treatment',
          submitted: submission,
        })
        .eq('id', sessionId)
        .eq('user_id', user.id)
        .eq('status', 'in_progress')
        .select('case_id')
        .single()
      if (updateError) throw updateError

      await trackCaseEvent({
        eventName: 'diagnosis_submitted',
        userId: user.id,
        sessionId,
        caseId: updatedSession.case_id,
        properties: {
          differentialCount: submission.differentials.length,
          evidenceCount: submission.evidence.length,
          confidence,
        },
      })

      router.push(`/case/${sessionId}/treat`)
    } catch {
      Alert.alert('错误', '提交失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <Text style={styles.heroEyebrow}>CLINICAL DECISION / 03</Text>
        <Text style={styles.heroTitle}>提交你的诊断判断</Text>
        <Text style={styles.heroText}>先给出最可能诊断，再说明鉴别对象与支持证据。系统会分别评分。</Text>
      </View>

      {/* 主要诊断 */}
      <SectionHeading index="01" title="主要诊断" required />
      <TextInput
        style={styles.input}
        value={primaryDiagnosis}
        onChangeText={setPrimaryDiagnosis}
        placeholder="请输入主要诊断..."
        placeholderTextColor={Colors.textTertiary}
      />
      <View style={styles.hint}>
        <Ionicons name="information-circle-outline" size={16} color={Colors.primary[700]} />
        <Text style={styles.hintText}>请根据问诊、查体和检查结果综合判断</Text>
      </View>

      {/* 鉴别诊断 */}
      <SectionHeading index="02" title="鉴别诊断" />
      {differentials.map((diff, i) => (
        <View key={i} style={styles.diffCard}>
          <View style={styles.diffHeader}>
            <Text style={styles.diffNumber}>{i + 1}</Text>
            {differentials.length > 1 && (
              <TouchableOpacity style={styles.removeButton} onPress={() => removeDifferential(i)}>
                <Ionicons name="close" size={17} color={Colors.error} />
              </TouchableOpacity>
            )}
          </View>
          <TextInput
            style={styles.diffInput}
            value={diff.diagnosis}
            onChangeText={(v) => updateDifferential(i, 'diagnosis', v)}
            placeholder="鉴别诊断..."
            placeholderTextColor={Colors.textTertiary}
          />
          <TextInput
            style={styles.diffReasoningInput}
            value={diff.reasoning}
            onChangeText={(v) => updateDifferential(i, 'reasoning', v)}
            placeholder="排除理由..."
            placeholderTextColor={Colors.textTertiary}
            multiline
          />
        </View>
      ))}
      {differentials.length < 5 && (
        <TouchableOpacity style={styles.addButton} onPress={addDifferential}>
          <Ionicons name="add" size={17} color={Colors.primary[700]} />
          <Text style={styles.addButtonText}>添加鉴别诊断</Text>
        </TouchableOpacity>
      )}

      {/* 诊断依据 */}
      <SectionHeading index="03" title="诊断依据" required />
      {evidence.map((ev, i) => (
        <View key={i} style={styles.evidenceRow}>
          <Text style={styles.evidenceNumber}>{i + 1}.</Text>
          <TextInput
            style={styles.evidenceInput}
            value={ev}
            onChangeText={(v) => updateEvidence(i, v)}
            placeholder="诊断依据..."
            placeholderTextColor={Colors.textTertiary}
          />
        </View>
      ))}
      {evidence.length < 8 && (
        <TouchableOpacity style={styles.addButton} onPress={addEvidence}>
          <Ionicons name="add" size={17} color={Colors.primary[700]} />
          <Text style={styles.addButtonText}>添加依据</Text>
        </TouchableOpacity>
      )}

      <SectionHeading index="04" title="提交前校准" />
      <View style={styles.calibrationCard}>
        <Text style={styles.calibrationLabel}>你对当前判断有多确定？</Text>
        <View style={styles.confidenceRow}>
          {[
            { value: 1 as const, label: '不确定' },
            { value: 2 as const, label: '较确定' },
            { value: 3 as const, label: '很确定' },
          ].map((item) => (
            <TouchableOpacity
              key={item.value}
              style={[styles.confidenceChip, confidence === item.value && styles.confidenceChipActive]}
              onPress={() => setConfidence(item.value)}
            >
              <Text style={[
                styles.confidenceText,
                confidence === item.value && styles.confidenceTextActive,
              ]}>
                {item.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <TextInput
          style={styles.uncertaintyInput}
          value={uncertainty}
          onChangeText={setUncertainty}
          placeholder="此刻最拿不准的一个判断是什么？（选填）"
          placeholderTextColor={Colors.textTertiary}
          multiline
        />
        <Text style={styles.calibrationHint}>先记录感觉，结果出来后再校准，不影响评分。</Text>
      </View>

      {/* 提交 */}
      <TouchableOpacity
        style={[styles.submitButton, loading && styles.submitButtonDisabled]}
        onPress={handleSubmit}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <>
            <Text style={styles.submitButtonText}>提交诊断</Text>
            <Ionicons name="arrow-forward" size={18} color="#FFFDF9" />
          </>
        )}
      </TouchableOpacity>
    </ScrollView>
  )
}

function SectionHeading({ index, title, required = false }: { index: string; title: string; required?: boolean }) {
  return (
    <View style={styles.sectionHeading}>
      <Text style={styles.sectionIndex}>{index}</Text>
      <Text style={styles.sectionTitle}>{title}</Text>
      {required && <Text style={styles.requiredMark}>必填</Text>}
    </View>
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
  hero: {
    minHeight: 210,
    backgroundColor: Colors.ink,
    borderRadius: BorderRadius['2xl'],
    padding: Spacing.xl,
    marginBottom: Spacing.xl,
  },
  heroEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '800',
    letterSpacing: 1.5,
    color: '#9DC8B9',
  },
  heroTitle: {
    fontSize: 28,
    lineHeight: 35,
    fontWeight: '800',
    letterSpacing: -0.7,
    color: '#FFFDF9',
    marginTop: Spacing.lg,
  },
  heroText: {
    ...Typography.bodyMedium,
    lineHeight: 22,
    color: 'rgba(255, 253, 249, 0.62)',
    marginTop: Spacing.sm,
    maxWidth: 330,
  },
  sectionHeading: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: Spacing.lg,
    marginBottom: Spacing.md,
  },
  sectionIndex: {
    width: 30,
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textTertiary,
  },
  sectionTitle: {
    ...Typography.titleMedium,
    color: Colors.textPrimary,
    flex: 1,
  },
  requiredMark: {
    ...Typography.labelSmall,
    color: Colors.error,
  },
  input: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.base,
    ...Typography.bodyLarge,
    color: Colors.textPrimary,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 48,
  },
  hint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.xs,
    marginTop: Spacing.sm,
  },
  hintText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
  },
  diffCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  diffHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  diffNumber: {
    ...Typography.titleSmall,
    color: Colors.primary[500],
  },
  removeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FAF0ED',
  },
  diffInput: {
    backgroundColor: Colors.neutral[50],
    borderRadius: BorderRadius.md,
    padding: Spacing.sm,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  diffReasoningInput: {
    backgroundColor: Colors.neutral[50],
    borderRadius: BorderRadius.md,
    padding: Spacing.sm,
    ...Typography.bodySmall,
    color: Colors.textPrimary,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 60,
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
  evidenceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  evidenceNumber: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
    width: 20,
  },
  evidenceInput: {
    flex: 1,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    padding: Spacing.sm,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  calibrationCard: {
    backgroundColor: Colors.primary[50],
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.primary[200],
    padding: Spacing.base,
  },
  calibrationLabel: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
    marginBottom: Spacing.md,
  },
  confidenceRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  confidenceChip: {
    flex: 1,
    minHeight: 38,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: Colors.primary[200],
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  confidenceChipActive: {
    backgroundColor: Colors.ink,
    borderColor: Colors.ink,
  },
  confidenceText: {
    ...Typography.labelMedium,
    color: Colors.primary[700],
  },
  confidenceTextActive: {
    color: '#FFFDF9',
    fontWeight: '700',
  },
  uncertaintyInput: {
    minHeight: 72,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    textAlignVertical: 'top',
  },
  calibrationHint: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: Spacing.sm,
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

import React, { useState } from 'react'
import { View, Text, StyleSheet, TextInput, TouchableOpacity, Alert, ActivityIndicator, ScrollView } from 'react-native'
import { useLocalSearchParams, useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { evaluateWithRAG } from '@/services/ai'
import { useAuth } from '@/hooks/useAuth'
import { useSubmitReview } from '@/hooks/useSpacedRepetition'
import { Colors, Typography, Spacing, BorderRadius } from '@/constants/theme'
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer'
import { FeedbackLoopCard } from '@/components/FeedbackLoopCard'

export default function FeynmanScreen() {
  const router = useRouter()
  const params = useLocalSearchParams<{ id: string; title: string }>()
  const nodeTitle = params.title || '未知知识点'

  const [transcript, setTranscript] = useState('')
  const [loading, setLoading] = useState(false)
  const [isSlow, setIsSlow] = useState(false) // 15s 预警状态
  const [result, setResult] = useState<any>(null)
  const [revisionFocus, setRevisionFocus] = useState('')
  const [attempt, setAttempt] = useState(1)
  const { user } = useAuth()
  const submitReview = useSubmitReview()

  const handleEvaluate = async () => {
    if (!transcript.trim()) return
    setLoading(true)
    setIsSlow(false)
    try {
      const res = await evaluateWithRAG(
        nodeTitle,
        transcript,
        () => setIsSlow(true) // 15s 后触发回调
      )
      setResult(res)
      setRevisionFocus('')
      if (user?.id && params.id && res?.score != null) {
        submitReview.mutate({ userId: user.id, nodeId: params.id, score: res.score })
      }
    } catch (e: any) {
      if (e.message === 'TEXTBOOK_NOT_FOUND') {
        Alert.alert('无法评估', '当前知识点尚未入库教材原文，无法进行精准费曼评估。')
      } else {
        Alert.alert('评估失败', 'AI 思考超时，请尝试缩短复述内容或稍后再试')
      }
    } finally {
      setLoading(false)
      setIsSlow(false)
    }
  }

  const startRevision = () => {
    const focus = result?.missingPoints?.[0] || '让解释更准确、完整，并说清因果关系'
    setRevisionFocus(focus)
    setResult(null)
    setTranscript('')
    setAttempt((current) => current + 1)
  }

  if (!params.id || !params.title) {
    return (
      <View style={styles.container}>
        <View style={styles.emptyState}>
          <Text style={styles.emptyTitle}>请先选择知识点</Text>
          <TouchableOpacity style={styles.emptyButton} onPress={() => router.replace('/map')}>
            <Text style={styles.emptyButtonText}>前往知识地图</Text>
          </TouchableOpacity>
        </View>
      </View>
    )
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <Text style={styles.heroEyebrow}>FEYNMAN PRACTICE / {String(attempt).padStart(2, '0')}</Text>
          <View style={styles.heroMark}>
            <Ionicons name="chatbox-ellipses-outline" size={22} color="#FFFDF9" />
          </View>
        </View>
        <Text style={styles.title}>{nodeTitle}</Text>
        <Text style={styles.outputHint}>不看答案，先用自己的语言讲清定义、机制和关键因果。</Text>
      </View>

      {revisionFocus && (
        <FeedbackLoopCard
          eyebrow={`ATTEMPT ${String(attempt).padStart(2, '0')}`}
          title="这一轮只修一个盲点"
          summary={revisionFocus}
          action="不照抄原文，重新用自己的语言完整讲一遍。"
        />
      )}

      <TextInput
        style={styles.textInput}
        placeholder={revisionFocus ? '重新讲一遍，并补上这个盲点...' : '不看答案，先试着向别人解释这个知识点...'}
        placeholderTextColor={Colors.textTertiary}
        multiline
        numberOfLines={6}
        textAlignVertical="top"
        value={transcript}
        onChangeText={setTranscript}
      />

      <TouchableOpacity
        style={[styles.submitBtn, (loading || !transcript.trim()) && styles.submitBtnDisabled]}
        onPress={handleEvaluate}
        disabled={loading || !transcript.trim()}
      >
        {loading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator color="#fff" />
            {isSlow && <Text style={styles.slowText}>AI 正在深度查阅教材...</Text>}
          </View>
        ) : (
          <>
            <Text style={styles.submitBtnText}>提交这一版解释</Text>
            <Ionicons name="arrow-forward" size={18} color="#FFFDF9" />
          </>
        )}
      </TouchableOpacity>

      {result && (
        <View style={styles.resultWrapper}>
          <View style={styles.resultCard}>
            <View style={styles.scoreRow}>
              <Text style={styles.scoreValue}>{result.score}</Text>
              <Text style={styles.scoreUnit}>分</Text>
            </View>
            <Text style={styles.feedback}>{result.feedback}</Text>

            <Text style={styles.missingTitle}>建议补充：</Text>
            {result.missingPoints?.map((p: string, i: number) => (
              <Text key={i} style={styles.missingItem}>• {p}</Text>
            ))}

            <View style={styles.referenceRow}>
              <Text style={styles.referenceText}>评估依据：{result.reference}</Text>
            </View>
            <TouchableOpacity style={styles.reviseBtn} onPress={startRevision}>
              <Text style={styles.reviseBtnText}>根据盲点再讲一次</Text>
            </TouchableOpacity>
          </View>
          {/* 强制要求：AI 结果下方展示免责声明 */}
          <MedicalDisclaimer />
        </View>
      )}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { paddingHorizontal: Spacing.lg, paddingBottom: Spacing['4xl'] },
  hero: {
    minHeight: 230,
    backgroundColor: '#E7DCC9',
    borderRadius: BorderRadius['2xl'],
    padding: Spacing.xl,
    marginBottom: Spacing.lg,
  },
  heroTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heroEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '800',
    letterSpacing: 1.4,
    color: Colors.primary[700],
  },
  heroMark: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.ink,
  },
  title: {
    fontSize: 28,
    lineHeight: 36,
    fontWeight: '800',
    letterSpacing: -0.7,
    color: Colors.textPrimary,
    marginTop: Spacing.lg,
  },
  outputHint: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    lineHeight: 22,
    marginTop: Spacing.sm,
    maxWidth: 330,
  },
  textInput: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.base,
    minHeight: 190,
    marginBottom: Spacing.base,
    borderWidth: 1,
    borderColor: Colors.border
  },
  submitBtn: {
    minHeight: 50,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.ink,
    borderRadius: BorderRadius.full,
  },
  submitBtnDisabled: { opacity: 0.6 },
  submitBtnText: { ...Typography.labelLarge, color: '#fff' },
  loadingRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  slowText: { color: '#fff', fontSize: 12 },
  resultWrapper: { marginTop: Spacing.xl },
  resultCard: { backgroundColor: Colors.surface, padding: Spacing.xl, borderRadius: BorderRadius.xl, borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.sm },
  scoreRow: { alignItems: 'center', marginBottom: Spacing.base },
  scoreValue: { ...Typography.displayLarge, color: Colors.primary[700] },
  scoreUnit: { ...Typography.bodySmall, color: Colors.textTertiary },
  feedback: { ...Typography.bodyMedium, lineHeight: 22, marginBottom: Spacing.base },
  missingTitle: { ...Typography.labelMedium, color: Colors.error },
  missingItem: { ...Typography.bodySmall, color: Colors.textSecondary, marginTop: Spacing.xs },
  referenceRow: { marginTop: Spacing.base, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: Colors.border, paddingTop: Spacing.md },
  referenceText: { ...Typography.bodySmall, color: Colors.textTertiary },
  reviseBtn: { marginTop: Spacing.lg, minHeight: 46, borderRadius: BorderRadius.full, backgroundColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  reviseBtnText: { ...Typography.labelLarge, color: '#fff', fontWeight: '700' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyTitle: { ...Typography.titleSmall },
  emptyButton: { marginTop: Spacing.lg, minHeight: 44, paddingHorizontal: Spacing.xl, borderRadius: BorderRadius.full, backgroundColor: Colors.ink, alignItems: 'center', justifyContent: 'center' },
  emptyButtonText: { ...Typography.labelLarge, color: '#fff' },
})

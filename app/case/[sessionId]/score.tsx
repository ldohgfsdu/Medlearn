import { useEffect, useState } from 'react'
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Modal,
  TextInput,
  Alert,
} from 'react-native'
import { useLocalSearchParams, useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '@/hooks/useAuth'
import { useCaseSession } from '@/hooks/useCaseSession'
import { supabase } from '@/lib/supabase'
import { trackCaseEvent } from '@/services/analytics'
import { caseEngine } from '@/services/case-engine'
import type { ScoreReport } from '@/services/scoring-engine'
import { FeedbackLoopCard } from '@/components/FeedbackLoopCard'
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer'
import { getCaseFeedbackFocus } from '@/utils/learningFeedback'
import {
  getCalibrationFeedback,
  type ConfidenceLevel,
} from '@/utils/learningChallenge'
import {
  Colors,
  Typography,
  Spacing,
  BorderRadius,
  Shadows,
  getGrade,
  getMasteryColor,
} from '@/constants/theme'

export default function ScoreScreen() {
  const router = useRouter()
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>()
  const { user } = useAuth()
  const { data: sessionData, isLoading } = useCaseSession(sessionId)
  const [reportModalVisible, setReportModalVisible] = useState(false)
  const [issueDescription, setIssueDescription] = useState('')
  const [issueType, setIssueType] = useState<'medical_content' | 'scoring'>('medical_content')
  const [submittingIssue, setSubmittingIssue] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const report = sessionData?.score as unknown as ScoreReport | null

  useEffect(() => {
    if (sessionData?.score) {
      if (user && sessionId) {
        trackCaseEvent({
          eventName: 'feedback_viewed',
          userId: user.id,
          sessionId,
          caseId: sessionData.case_id,
          properties: {
            totalScore: (sessionData.score as any).totalScore,
          },
        })
      }
    }
  }, [sessionData, user, sessionId])

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary[500]} />
        <Text style={styles.loadingText}>正在生成学习报告...</Text>
      </View>
    )
  }

  if (!report) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.errorText}>未找到评分数据</Text>
      </View>
    )
  }

  const grade = getGrade(report.totalScore)
  const focus = getCaseFeedbackFocus(report)
  const submitted = sessionData?.submitted as {
    confidence?: ConfidenceLevel
    uncertainty?: string
  } | null
  const calibration = getCalibrationFeedback(
    submitted?.confidence,
    report.totalScore,
    submitted?.uncertainty
  )

  // AI 生成内容（反馈、校准建议等）必须展示免责
  // 评分主体是确定性算法，但伴随文本来自模型生成或总结。

  const retrySameCase = async () => {
    if (!user || !sessionData?.case_id || retrying) return
    setRetrying(true)
    try {
      const { sessionId: nextSessionId } = await caseEngine.startCase(sessionData.case_id, user.id)
      router.replace({
        pathname: '/case/[sessionId]/chat',
        params: {
          sessionId: nextSessionId,
          focus: focus.action,
        },
      })
    } catch {
      Alert.alert('启动失败', '暂时无法重做该病例，请稍后再试。')
      setRetrying(false)
    }
  }

  const submitMedicalIssue = async () => {
    if (!sessionId || !user || submittingIssue) return
    if (!issueDescription.trim()) {
      Alert.alert('提示', '请简单描述你发现的问题')
      return
    }

    setSubmittingIssue(true)
    try {
      const caseId = sessionData?.case_id

      const { error } = await supabase.from('medical_issue_reports').insert({
        user_id: user.id,
        session_id: sessionId,
        case_id: caseId,
        issue_type: issueType,
        description: issueDescription.trim(),
      })

      if (error) throw error

      await trackCaseEvent({
        eventName:
          issueType === 'scoring'
            ? 'scoring_dispute_submitted'
            : 'medical_issue_reported',
        userId: user.id,
        sessionId,
        caseId,
        properties: {
          issueType,
        },
      })

      setIssueDescription('')
      setReportModalVisible(false)
      Alert.alert('已提交', '谢谢反馈，我们会在医学审核流程中处理这个问题。')
    } catch {
      Alert.alert('提交失败', '请稍后再试')
    } finally {
      setSubmittingIssue(false)
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* 总分 */}
      <View style={styles.heroCard}>
        <Text style={styles.heroLabel}>第一版作品已完成</Text>
        <View style={styles.scoreRing}>
          <Text style={[styles.scoreValue, { color: grade.color }]}>{report.totalScore}</Text>
          <Text style={styles.scoreUnit}>/ 100</Text>
        </View>
        <Text style={[styles.gradeText, { color: grade.color }]}>{grade.label}</Text>
        <Text style={styles.heroNote}>分数只负责定位，不负责定义你。</Text>
      </View>

      <FeedbackLoopCard
        title={focus.title}
        summary={`${focus.summary} 当前完成度 ${focus.percent}%。`}
        action={focus.action}
      />

      <MedicalDisclaimer />

      {calibration && (
        <FeedbackLoopCard
          eyebrow="METACOGNITION"
          title={calibration.title}
          summary={calibration.summary}
          action={calibration.action}
        />
      )}

      {/* 维度分数 */}
      <View style={styles.dimensionsCard}>
        <DimensionBar label="诊断准确性" score={report.diagnosis.score} max={report.diagnosis.maxScore} />
        <DimensionBar label="鉴别诊断" score={report.differential.score} max={report.differential.maxScore} />
        <DimensionBar label="证据运用" score={report.evidence.score} max={report.evidence.maxScore} />
        <DimensionBar label="治疗方案" score={report.treatment.score} max={report.treatment.maxScore} />
      </View>

      {/* 诊断分析 */}
      {report.diagnosis.analysis && (
        <View style={styles.sectionCard}>
          <ReportHeading icon="medkit-outline" title="诊断分析" />
          <Text style={styles.sectionText}>{report.diagnosis.analysis}</Text>
        </View>
      )}

      {/* 治疗分析 */}
      {report.treatment.details.length > 0 && (
        <View style={styles.sectionCard}>
          <ReportHeading icon="flask-outline" title="治疗分析" />
          {report.treatment.details.map((detail, i) => (
            <View key={i} style={styles.detailRow}>
              <Text style={styles.detailFeedback}>{detail.feedback}</Text>
            </View>
          ))}
        </View>
      )}

      {/* 优势 */}
      {report.strengths.length > 0 && (
        <View style={styles.sectionCard}>
          <ReportHeading icon="checkmark-circle-outline" title="优势" />
          {report.strengths.map((s, i) => (
            <Text key={i} style={styles.listItem}>• {s}</Text>
          ))}
        </View>
      )}

      {/* 不足 */}
      {report.weaknesses.length > 0 && (
        <View style={styles.sectionCard}>
          <ReportHeading icon="alert-circle-outline" title="需要改进" />
          {report.weaknesses.map((w, i) => (
            <Text key={i} style={styles.listItem}>• {w}</Text>
          ))}
        </View>
      )}

      {/* 学习建议 */}
      {report.recommendations.length > 0 && (
        <View style={styles.sectionCard}>
          <ReportHeading icon="book-outline" title="学习建议" />
          {report.recommendations.map((r, i) => (
            <Text key={i} style={styles.listItem}>{i + 1}. {r}</Text>
          ))}
        </View>
      )}

      {/* 操作按钮 */}
      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={retrySameCase}
          disabled={retrying}
        >
          {retrying ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.primaryButtonText}>带着反馈重做本病例</Text>
          )}
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => router.replace('/(tabs)/cases')}
        >
          <Text style={styles.secondaryButtonText}>换一个病例</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => router.replace('/(tabs)')}
        >
          <Text style={styles.secondaryButtonText}>返回首页</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.reportButton}
          onPress={() => {
            setIssueType('medical_content')
            setReportModalVisible(true)
          }}
        >
          <Text style={styles.reportButtonText}>报告医学内容问题</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.reportButton}
          onPress={() => {
            setIssueType('scoring')
            setReportModalVisible(true)
          }}
        >
          <Text style={styles.reportButtonText}>申诉评分结果</Text>
        </TouchableOpacity>
      </View>
      <Modal
        transparent
        animationType="fade"
        visible={reportModalVisible}
        onRequestClose={() => setReportModalVisible(false)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.issueCard}>
            <Text style={styles.issueTitle}>
              {issueType === 'scoring' ? '申诉评分结果' : '报告医学内容问题'}
            </Text>
            <Text style={styles.issueHelp}>
              {issueType === 'scoring'
                ? '请说明你认为评分与提交内容不一致的部分。'
                : '如果病例或反馈存在医学错误、不安全建议或诊断泄露，请告诉我们。'}
            </Text>
            <TextInput
              style={styles.issueInput}
              value={issueDescription}
              onChangeText={setIssueDescription}
              placeholder="例如：治疗建议遗漏了关键处理，或评分理由不合理..."
              placeholderTextColor={Colors.textTertiary}
              multiline
              textAlignVertical="top"
            />
            <View style={styles.issueActions}>
              <TouchableOpacity
                style={styles.issueSecondaryButton}
                onPress={() => setReportModalVisible(false)}
                disabled={submittingIssue}
              >
                <Text style={styles.issueSecondaryText}>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.issuePrimaryButton, submittingIssue && styles.issuePrimaryButtonDisabled]}
                onPress={submitMedicalIssue}
                disabled={submittingIssue}
              >
                {submittingIssue ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.issuePrimaryText}>提交</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  )
}

function ReportHeading({ icon, title }: { icon: keyof typeof Ionicons.glyphMap; title: string }) {
  return (
    <View style={styles.sectionHeading}>
      <View style={styles.sectionIcon}>
        <Ionicons name={icon} size={17} color={Colors.primary[700]} />
      </View>
      <Text style={styles.sectionTitle}>{title}</Text>
    </View>
  )
}

function DimensionBar({ label, score, max }: { label: string; score: number; max: number }) {
  const percent = max > 0 ? (score / max) * 100 : 0
  const color = getMasteryColor(percent)

  return (
    <View style={styles.dimensionRow}>
      <Text style={styles.dimensionLabel}>{label}</Text>
      <View style={styles.dimensionBarBg}>
        <View style={[styles.dimensionBarFill, { width: `${percent}%`, backgroundColor: color }]} />
      </View>
      <Text style={styles.dimensionScore}>{score}/{max}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    padding: Spacing.base,
    paddingBottom: Spacing['3xl'],
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
  },
  loadingText: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    marginTop: Spacing.md,
  },
  errorText: {
    ...Typography.bodyMedium,
    color: Colors.textTertiary,
  },
  // 总分
  heroCard: {
    backgroundColor: Colors.ink,
    padding: Spacing['2xl'],
    borderRadius: BorderRadius.xl,
    alignItems: 'center',
    marginBottom: Spacing.lg,
    ...Shadows.level2,
  },
  heroLabel: {
    ...Typography.bodySmall,
    color: '#9DC8B9',
    marginBottom: Spacing.md,
  },
  scoreRing: {
    alignItems: 'center',
  },
  scoreValue: {
    fontSize: 64,
    fontWeight: 'bold',
  },
  scoreUnit: {
    ...Typography.bodyMedium,
    color: 'rgba(255, 253, 249, 0.52)',
  },
  gradeText: {
    ...Typography.titleLarge,
    marginTop: Spacing.sm,
  },
  heroNote: {
    ...Typography.bodySmall,
    color: 'rgba(255, 253, 249, 0.52)',
    marginTop: Spacing.sm,
  },
  // 维度
  dimensionsCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.lg,
    ...Shadows.level1,
  },
  dimensionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  dimensionLabel: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
    width: 72,
  },
  dimensionBarBg: {
    flex: 1,
    height: 8,
    backgroundColor: Colors.neutral[200],
    borderRadius: 4,
    marginHorizontal: Spacing.sm,
    overflow: 'hidden',
  },
  dimensionBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  dimensionScore: {
    ...Typography.labelSmall,
    color: Colors.textSecondary,
    width: 40,
    textAlign: 'right',
  },
  // 分析段落
  sectionCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  sectionHeading: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  sectionIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
  },
  sectionTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  sectionText: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    lineHeight: 22,
  },
  detailRow: {
    paddingVertical: Spacing.xs,
  },
  detailFeedback: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
  },
  listItem: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    lineHeight: 22,
    marginBottom: Spacing.xs,
  },
  // 操作
  actions: {
    gap: Spacing.md,
    marginTop: Spacing.lg,
  },
  primaryButton: {
    backgroundColor: Colors.ink,
    padding: Spacing.base,
    borderRadius: BorderRadius.full,
    alignItems: 'center',
    minHeight: 48,
    justifyContent: 'center',
  },
  primaryButtonText: {
    ...Typography.labelLarge,
    color: '#fff',
  },
  secondaryButton: {
    backgroundColor: Colors.surface,
    padding: Spacing.base,
    borderRadius: BorderRadius.full,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  secondaryButtonText: {
    ...Typography.labelLarge,
    color: Colors.textPrimary,
  },
  reportButton: {
    padding: Spacing.base,
    alignItems: 'center',
  },
  reportButtonText: {
    ...Typography.labelMedium,
    color: Colors.textTertiary,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(17, 24, 39, 0.55)',
    justifyContent: 'center',
    padding: Spacing.lg,
  },
  issueCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.xl,
    ...Shadows.level2,
  },
  issueTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
    marginBottom: Spacing.sm,
  },
  issueHelp: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    lineHeight: 22,
    marginBottom: Spacing.md,
  },
  issueInput: {
    minHeight: 120,
    backgroundColor: Colors.neutral[50],
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
  },
  issueActions: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: Spacing.lg,
  },
  issueSecondaryButton: {
    flex: 1,
    minHeight: 44,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  issueSecondaryText: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
  },
  issuePrimaryButton: {
    flex: 1,
    minHeight: 44,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
  },
  issuePrimaryButtonDisabled: {
    opacity: 0.6,
  },
  issuePrimaryText: {
    ...Typography.labelMedium,
    color: '#fff',
  },
})

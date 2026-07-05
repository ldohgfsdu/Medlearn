import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ActivityIndicator,

  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, useLocalSearchParams, useRouter } from 'expo-router'
import { SwipeableTabPager } from '@/components/SwipeableTabPager'
import { FeedbackLoopCard } from '@/components/FeedbackLoopCard'
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer'
import { useDiseaseDetail, type DiseaseKnowledgeNode } from '@/hooks/useDiseaseDetail'
import { useAuth } from '@/hooks/useAuth'
import { useSubmitReview } from '@/hooks/useSpacedRepetition'
import { evaluateWithRAG, type EvaluationResult } from '@/services/ai'
import { saveFeynmanRecord } from '@/services/feynman'
import { buildFeynmanScaffold } from '@/utils/feynmanOutline'
import {
  groupDiseaseKnowledgeNodes,
  hasKnowledgeEvidence,
  knowledgeNodeItemText,
  knowledgeNodeText,
} from '@/utils/diseaseKnowledge'
import { parseContentPoints } from '@/utils/structuredContent'
import { appAlert } from '@/lib/app-dialog'
import { Colors, FontFamily, Spacing, Typography, BorderRadius } from '@/constants/theme'
import { Layout } from '@/constants/layout'

type TabKey = 'knowledge' | 'reasoning' | 'training'

interface ReasoningOption {
  id: string
  text: string
}

interface ReasoningStep {
  id: string
  prompt: string
  explanation: string
  options: ReasoningOption[]
  correctOptionId: string
}

function introFromNodes(nodes: DiseaseKnowledgeNode[], name: string) {
  const evidenced = nodes.filter((node) => hasKnowledgeEvidence(node.source_span))
  const source = evidenced.find((node) => node.aspect === 'definition') ?? evidenced[0]
  if (!source) return `${name}的教材知识正在整理中。`
  const text = knowledgeNodeText(source)
  return parseContentPoints(text)[0]?.body || text.slice(0, 220)
}

function normalizeReasoningSteps(value: unknown): ReasoningStep[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((raw, index) => {
    if (!raw || typeof raw !== 'object') return []
    const step = raw as Record<string, unknown>
    const rawOptions = Array.isArray(step.options) ? step.options : []
    const options = rawOptions.flatMap((option, optionIndex) => {
      if (typeof option === 'string') {
        return [{ id: String(optionIndex), text: option }]
      }
      if (!option || typeof option !== 'object') return []
      const item = option as Record<string, unknown>
      const text = item.text ?? item.label
      if (typeof text !== 'string') return []
      return [{ id: String(item.id ?? optionIndex), text }]
    })
    const correctOptionId = String(step.correct_option_id ?? step.correctOptionId ?? '')
    const prompt = step.prompt ?? step.question
    const optionIds = new Set(options.map((option) => option.id))
    const optionTexts = new Set(options.map((option) => option.text.trim()))
    if (
      options.length !== 4
      || optionIds.size !== 4
      || optionTexts.size !== 4
      || !correctOptionId
      || !optionIds.has(correctOptionId)
      || typeof prompt !== 'string'
    ) return []
    return [{
      id: String(step.id ?? index),
      prompt,
      explanation: typeof step.explanation === 'string' ? step.explanation : '',
      options,
      correctOptionId,
    }]
  })
}

function KnowledgeTab({ nodes, initialAspect }: { nodes: DiseaseKnowledgeNode[]; initialAspect?: string }) {
  const groups = useMemo(() => groupDiseaseKnowledgeNodes(nodes), [nodes])
  const targetKey = initialAspect ? `aspect:${initialAspect}` : null
  const [expandedId, setExpandedId] = useState<string | null>(targetKey)
  const scrollRef = useRef<ScrollView>(null)
  const positions = useRef<Record<string, number>>({})

  useEffect(() => {
    if (!targetKey || !groups.some((group) => group.key === targetKey)) return
    const timer = setTimeout(() => {
      scrollRef.current?.scrollTo({ y: Math.max(0, (positions.current[targetKey] ?? 0) - 12), animated: true })
    }, 120)
    return () => clearTimeout(timer)
  }, [groups, targetKey])

  return (
    <ScrollView ref={scrollRef} style={styles.tabScroll} contentContainerStyle={styles.tabContent}>
      {groups.length ? groups.map((group) => {
        const expanded = expandedId === group.key
        return (
          <View
            key={group.key}
            style={styles.card}
            onLayout={(event) => {
              positions.current[group.key] = event.nativeEvent.layout.y
              if (group.key === targetKey) {
                scrollRef.current?.scrollTo({ y: Math.max(0, event.nativeEvent.layout.y - 12), animated: true })
              }
            }}
          >
            <TouchableOpacity style={styles.cardHeader} onPress={() => setExpandedId(expanded ? null : group.key)}>
              <Text style={styles.cardTitle}>{group.title}</Text>
              <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={18} color={Colors.textTertiary} />
            </TouchableOpacity>
            {expanded && group.nodes.length === 1 ? (
              hasKnowledgeEvidence(group.nodes[0].source_span) ? (
                <>
                  <Text style={styles.cardBody}>{knowledgeNodeText(group.nodes[0])}</Text>
                  <EvidenceDisclosure node={group.nodes[0]} />
                </>
              ) : (
                <Text style={styles.evidencePending}>教材证据核对中，要点暂不展示。</Text>
              )
            ) : null}
            {expanded && group.nodes.length > 1 ? group.nodes.map((node, index) => (
              <View key={node.id} style={[styles.knowledgeItem, index > 0 && styles.knowledgeItemBorder]}>
                <View style={styles.knowledgeItemHeader}>
                  <Text style={styles.knowledgeItemNumber}>{index + 1}</Text>
                  <Text style={styles.knowledgeItemTitle}>
                    {node.display_title || node.title}
                  </Text>
                </View>
                {hasKnowledgeEvidence(node.source_span) ? (
                  <>
                    <Text style={styles.knowledgeItemBody}>{knowledgeNodeItemText(node)}</Text>
                    <EvidenceDisclosure node={node} />
                  </>
                ) : (
                  <Text style={styles.evidencePending}>教材证据核对中，要点暂不展示。</Text>
                )}
              </View>
            )) : null}
          </View>
        )
      }) : <Empty icon="book-outline" title="暂无知识内容" />}
    </ScrollView>
  )
}

function EvidenceDisclosure({ node }: { node: DiseaseKnowledgeNode }) {
  const [visible, setVisible] = useState(false)
  const source = node.source_span
  if (!hasKnowledgeEvidence(source)) return null
  const evidenceItems = source?.evidence_items?.filter((item) => item.trim()) ?? []
  const evidence = evidenceItems.length
    ? evidenceItems
    : source?.evidence?.trim()
      ? [source.evidence.trim()]
      : []
  const pageStart = source?.page_start ?? source?.provenance?.page_start
  const pageEnd = source?.page_end ?? source?.provenance?.page_end
  const pageLabel = pageStart
    ? pageEnd && pageEnd !== pageStart
      ? `第 ${pageStart}–${pageEnd} 页`
      : `第 ${pageStart} 页`
    : '页码待核对'

  return (
    <View style={styles.evidenceBlock}>
      <TouchableOpacity style={styles.evidenceToggle} onPress={() => setVisible((value) => !value)}>
        <Ionicons name="document-text-outline" size={16} color={Colors.primary[700]} />
        <Text style={styles.evidenceToggleText}>
          {visible ? '收起教材原文' : '查看教材原文'} · {pageLabel}
        </Text>
      </TouchableOpacity>
      {visible ? evidence.map((item, index) => (
        <Text key={`${node.id}-evidence-${index}`} style={styles.evidenceText}>
          {evidence.length > 1 ? `${index + 1}. ` : ''}{item}
        </Text>
      )) : null}
    </View>
  )
}

function ReasoningTab({ chain }: { chain: Record<string, unknown> | null | undefined }) {
  const steps = useMemo(() => normalizeReasoningSteps(chain?.steps), [chain])
  const [stepIndex, setStepIndex] = useState(0)
  const [attempts, setAttempts] = useState<Record<string, number>>({})
  const [selected, setSelected] = useState<Record<string, string>>({})

  if (!chain || chain.validation_status === 'pending' || chain.validation_status === 'review_required') {
    return <Empty icon="git-branch-outline" title="推导训练暂未开放" detail="推导链通过教材证据和医学逻辑校验后开放。" />
  }
  if (chain.validation_status !== 'valid' || steps.length < 4 || steps.length > 8) {
    return <Empty icon="shield-outline" title="推导链未通过质量门槛" detail="无效链仅保留在开发审计中。" />
  }

  const step = steps[stepIndex]
  const attempt = attempts[step.id] ?? 0
  const selectedId = selected[step.id]
  const correct = selectedId === step.correctOptionId
  const revealed = attempt >= 2

  const choose = (optionId: string) => {
    if (correct || revealed) return
    setSelected((current) => ({ ...current, [step.id]: optionId }))
    if (optionId !== step.correctOptionId) {
      setAttempts((current) => ({ ...current, [step.id]: (current[step.id] ?? 0) + 1 }))
    }
  }

  return (
    <ScrollView style={styles.tabScroll} contentContainerStyle={styles.tabContent}>
      <Text style={styles.progress}>第 {stepIndex + 1} / {steps.length} 步</Text>
      <View style={styles.card}>
        <Text style={styles.reasonPrompt}>{step.prompt}</Text>
        {step.options.map((option) => {
          const isSelected = selectedId === option.id
          const showCorrect = (correct || revealed) && option.id === step.correctOptionId
          return (
            <TouchableOpacity
              key={option.id}
              style={[styles.option, isSelected && styles.optionSelected, showCorrect && styles.optionCorrect]}
              onPress={() => choose(option.id)}
            >
              <Text style={styles.optionText}>{option.text}</Text>
            </TouchableOpacity>
          )
        })}
        {attempt === 1 && !correct ? <Text style={styles.feedbackError}>方向不对。请重新检查这一步的因果关系，暂不公布答案。</Text> : null}
        {(correct || revealed) && step.explanation ? <Text style={styles.explanation}>{step.explanation}</Text> : null}
        {(correct || revealed) && stepIndex < steps.length - 1 ? (
          <TouchableOpacity style={styles.primaryButton} onPress={() => setStepIndex((value) => value + 1)}>
            <Text style={styles.primaryButtonText}>下一步</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      <MedicalDisclaimer />
    </ScrollView>
  )
}

function TrainingTab({ name, nodes }: { name: string; nodes: DiseaseKnowledgeNode[] }) {
  const primaryNode = nodes[0]
  const { user } = useAuth()
  const submitReview = useSubmitReview()
  const [transcript, setTranscript] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<EvaluationResult | null>(null)
  const [revisionFocus, setRevisionFocus] = useState('')
  const [attempt, setAttempt] = useState(1)

  const scaffold = useMemo(() => primaryNode ? buildFeynmanScaffold({
    title: name,
    type: 'disease',
    content: nodes.map(knowledgeNodeText).join('\n\n'),
    keyPoints: nodes.flatMap((node) => node.key_points ?? []),
    structuredSections: nodes.flatMap((node) => node.structured_sections ?? []).map((item) => ({
      title: item.title ?? '',
      content: item.content ?? '',
    })),
  }) : null, [name, nodes, primaryNode])

  const evaluate = async () => {
    if (!primaryNode || !transcript.trim()) return
    setLoading(true)
    try {
      const next = await evaluateWithRAG(name, transcript, undefined, { nodeId: primaryNode.id, attempt })
      setResult(next)
      setRevisionFocus('')
      if (user?.id) {
        await Promise.all([
          saveFeynmanRecord({ userId: user.id, nodeId: primaryNode.id, transcript, result: next, attempt }),
          submitReview.mutateAsync({ userId: user.id, nodeId: primaryNode.id, score: next.score }),
        ])
      }
    } catch (error) {
      appAlert('评估失败', error instanceof Error && error.message === 'TEXTBOOK_NOT_FOUND'
        ? '当前疾病尚未关联可检索的教材原文。'
        : 'AI 评估暂时不可用，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  const revise = () => {
    setRevisionFocus(result?.missingPoints?.[0] || result?.nextSentence || '补全关键机制和因果关系。')
    setResult(null)
    setTranscript('')
    setAttempt((value) => value + 1)
  }

  if (!primaryNode || !scaffold) return <Empty icon="create-outline" title="训练暂未开放" />

  return (
    <ScrollView style={styles.tabScroll} contentContainerStyle={styles.tabContent} keyboardShouldPersistTaps="handled">
      <View style={styles.card}>
        <Text style={styles.cardTitle}>费曼复述提纲</Text>
        <Text style={styles.hint}>{scaffold.intro}</Text>
        {scaffold.mustCover.map((point) => <Text key={point} style={styles.bullet}>• {point}</Text>)}
      </View>
      {revisionFocus ? <FeedbackLoopCard title="这一轮只修一个盲点" summary={revisionFocus} action="不用照抄原文，重新完整讲一遍。" /> : null}
      <TextInput
        style={styles.input}
        multiline
        textAlignVertical="top"
        value={transcript}
        onChangeText={setTranscript}
        placeholder="不看答案，用自己的语言完整解释这个疾病..."
        placeholderTextColor={Colors.textTertiary}
      />
      <TouchableOpacity style={[styles.primaryButton, (!transcript.trim() || loading) && styles.disabled]} onPress={evaluate} disabled={!transcript.trim() || loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>提交评估</Text>}
      </TouchableOpacity>
      {result ? (
        <View style={styles.card}>
          <Text style={styles.score}>{result.score} 分</Text>
          <Text style={styles.cardBody}>{result.feedback}</Text>
          {result.missingPoints.map((point) => <Text key={point} style={styles.bullet}>• {point}</Text>)}
          <TouchableOpacity style={styles.secondaryButton} onPress={revise}><Text style={styles.secondaryButtonText}>根据盲点再讲一次</Text></TouchableOpacity>
          <MedicalDisclaimer />
        </View>
      ) : null}
    </ScrollView>
  )
}

function Empty({ icon, title, detail }: { icon: React.ComponentProps<typeof Ionicons>['name']; title: string; detail?: string }) {
  return (
    <View style={styles.empty}>
      <Ionicons name={icon} size={40} color={Colors.neutral[300]} />
      <Text style={styles.emptyTitle}>{title}</Text>
      {detail ? <Text style={styles.emptyDetail}>{detail}</Text> : null}
    </View>
  )
}

export default function DiseaseDetailScreen() {
  const params = useLocalSearchParams<{ id?: string; tab?: TabKey; aspect?: string }>()
  const router = useRouter()
  const { data, isLoading } = useDiseaseDetail(params.id ?? '')
  const initialIndex = Math.max(0, ['knowledge', 'reasoning', 'training'].indexOf(params.tab ?? 'knowledge'))

  if (isLoading) return <View style={styles.center}><ActivityIndicator color={Colors.primary[700]} /></View>
  if (!data) {
    return (
      <View style={styles.center}>
        <Text style={styles.emptyTitle}>疾病不存在、未确认或暂不可访问</Text>
        <TouchableOpacity onPress={() => router.back()}><Text style={styles.backLink}>返回</Text></TouchableOpacity>
      </View>
    )
  }

  const name = data.entity.canonical_disease_name
  if (data.entity.content_status !== 'available') {
    return (
      <View style={styles.container}>
        <Stack.Screen options={{ headerShown: false }} />
        <View style={styles.header}>
          <TouchableOpacity style={styles.back} onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={18} color={Colors.textSecondary} />
            <Text style={styles.backText}>返回</Text>
          </TouchableOpacity>
          <Text style={styles.title}>{name}</Text>
          <Text style={styles.aliases}>所属目录位置已建立</Text>
        </View>
        <Empty
          icon="time-outline"
          title="整理中"
          detail="当前仅保留目录位置，不展示未完成知识内容。"
        />
      </View>
    )
  }
  const breadcrumb = data.sections.map((section) => section.catalog_path).filter(Boolean).join('；')

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <TouchableOpacity style={styles.back} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={18} color={Colors.textSecondary} />
          <Text style={styles.backText}>返回</Text>
        </TouchableOpacity>
        {breadcrumb ? <Text style={styles.breadcrumb}>{breadcrumb}</Text> : null}
        <Text style={styles.title}>{name}</Text>
        {data.entity.aliases?.length ? <Text style={styles.aliases}>别名：{data.entity.aliases.join('、')}</Text> : null}
        <Text style={styles.intro}>{introFromNodes(data.nodes, name)}</Text>
      </View>
      <SwipeableTabPager
        initialIndex={initialIndex}
        tabs={[
          { key: 'knowledge', label: '知识', icon: 'book-outline' },
          { key: 'reasoning', label: '推导', icon: 'git-branch-outline' },
          { key: 'training', label: '训练', icon: 'create-outline' },
        ]}
        pages={[
          <KnowledgeTab key="knowledge" nodes={data.nodes} initialAspect={params.aspect} />,
          <ReasoningTab key="reasoning" chain={data.chain as Record<string, unknown> | null} />,
          <TrainingTab key="training" name={name} nodes={data.nodes} />,
        ]}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl, backgroundColor: Colors.background },
  header: { paddingHorizontal: Layout.screenPaddingX, paddingVertical: Spacing.md, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: Colors.border },
  back: { flexDirection: 'row', alignItems: 'center', minHeight: 44, marginBottom: Spacing.sm },
  backText: { ...Typography.labelMedium, color: Colors.textSecondary },
  backLink: { ...Typography.labelLarge, color: Colors.primary[700], marginTop: Spacing.md },
  breadcrumb: { ...Typography.labelSmall, color: Colors.textTertiary },
  title: { ...Typography.titleLarge, fontFamily: FontFamily.serif, color: Colors.textPrimary, marginTop: Spacing.xs },
  aliases: { ...Typography.bodyMedium, color: Colors.textTertiary, lineHeight: 21, marginTop: 2 },
  intro: { ...Typography.bodyMedium, color: Colors.textSecondary, lineHeight: 23, marginTop: Spacing.sm },
  tabScroll: { flex: 1 },
  tabContent: { padding: Layout.screenPaddingX, paddingBottom: Layout.screenPaddingBottom },
  card: { backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, borderRadius: Layout.cardRadius, padding: Layout.cardPadding, marginBottom: Spacing.sm },
  cardHeader: { minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  cardTitle: { ...Typography.titleSmall, fontFamily: FontFamily.serif, color: Colors.textPrimary, flex: 1 },
  cardBody: { ...Typography.bodyMedium, color: Colors.textPrimary, lineHeight: 24, marginTop: Spacing.sm },
  knowledgeItem: { paddingTop: Spacing.sm, paddingBottom: Spacing.xs },
  knowledgeItemBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: Colors.border, marginTop: Spacing.sm },
  knowledgeItemHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm },
  knowledgeItemNumber: { ...Typography.labelMedium, color: Colors.primary[700], minWidth: 18 },
  knowledgeItemTitle: { ...Typography.labelLarge, fontFamily: FontFamily.serif, color: Colors.textPrimary, flex: 1 },
  knowledgeItemBody: { ...Typography.bodyMedium, color: Colors.textSecondary, lineHeight: 23, marginTop: Spacing.xs, marginLeft: 26 },
  evidenceBlock: { marginTop: Spacing.sm, marginLeft: 26, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: Colors.border, paddingTop: Spacing.sm },
  evidenceToggle: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs, minHeight: 44 },
  evidenceToggleText: { ...Typography.labelMedium, color: Colors.primary[700], flex: 1 },
  evidenceText: { ...Typography.bodyMedium, color: Colors.textSecondary, lineHeight: 22, marginTop: Spacing.xs },
  evidencePending: { ...Typography.bodyMedium, color: Colors.textTertiary, lineHeight: 22, marginTop: Spacing.sm, fontStyle: 'italic' },
  hint: { ...Typography.bodyMedium, color: Colors.textSecondary, lineHeight: 22, marginTop: Spacing.xs, marginBottom: Spacing.sm },
  bullet: { ...Typography.bodyMedium, color: Colors.textSecondary, lineHeight: 22, marginTop: 3 },
  progress: { ...Typography.labelMedium, color: Colors.primary[700], marginBottom: Spacing.sm },
  reasonPrompt: { ...Typography.titleMedium, fontFamily: FontFamily.serif, color: Colors.textPrimary, marginBottom: Spacing.md },
  option: { minHeight: 46, justifyContent: 'center', paddingHorizontal: Spacing.md, borderWidth: 1, borderColor: Colors.border, borderRadius: BorderRadius.lg, marginBottom: Spacing.sm },
  optionSelected: { borderColor: Colors.primary[500], backgroundColor: Colors.primary[50] },
  optionCorrect: { borderColor: Colors.success, backgroundColor: '#ECFDF5' },
  optionText: { ...Typography.bodyMedium, color: Colors.textPrimary },
  feedbackError: { ...Typography.bodyMedium, color: Colors.error, lineHeight: 21, marginTop: Spacing.sm },
  explanation: { ...Typography.bodyMedium, color: Colors.textSecondary, lineHeight: 22, marginTop: Spacing.md },
  input: { minHeight: 180, padding: Spacing.base, borderWidth: 1, borderColor: Colors.border, borderRadius: BorderRadius.lg, backgroundColor: Colors.surface, ...Typography.bodyMedium, color: Colors.textPrimary, marginBottom: Spacing.md },
  primaryButton: { minHeight: 46, alignItems: 'center', justifyContent: 'center', borderRadius: BorderRadius.full, backgroundColor: Colors.primary[700], marginTop: Spacing.md },
  primaryButtonText: { ...Typography.labelLarge, color: '#fff', fontWeight: '600' },
  secondaryButton: { minHeight: 44, alignItems: 'center', justifyContent: 'center', borderRadius: BorderRadius.full, backgroundColor: Colors.ink, marginTop: Spacing.md },
  secondaryButtonText: { ...Typography.labelMedium, color: '#fff', fontWeight: '600' },
  disabled: { opacity: 0.5 },
  score: { ...Typography.titleLarge, color: Colors.primary[700], textAlign: 'center' },
  empty: { minHeight: 240, alignItems: 'center', justifyContent: 'center', padding: Spacing.xl },
  emptyTitle: { ...Typography.titleMedium, color: Colors.textPrimary, marginTop: Spacing.md, textAlign: 'center' },
  emptyDetail: { ...Typography.bodyMedium, color: Colors.textTertiary, lineHeight: 21, marginTop: Spacing.xs, textAlign: 'center' },
})

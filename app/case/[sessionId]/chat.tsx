import { useState, useRef, useEffect } from 'react'
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
} from 'react-native'
import { useLocalSearchParams, useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '@/hooks/useAuth'
import { useCaseSession } from '@/hooks/useCaseSession'
import { supabase } from '@/lib/supabase'
import { caseEngine, type CaseState, type CaseMessage } from '@/services/case-engine'
import { abandonCase } from '@/services/case-abandon'
import { Colors, Typography, Spacing, BorderRadius } from '@/constants/theme'
import { CasePhase, PHASE_LABELS, EXAM_REGIONS, LAB_TESTS } from '@/constants/vindicate'
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer'

let localMessageSequence = 0

function createLocalMessageId(prefix: string): string {
  localMessageSequence += 1
  return `${prefix}-${localMessageSequence}`
}

export default function CaseChatScreen() {
  const router = useRouter()
  const { sessionId, focus } = useLocalSearchParams<{ sessionId: string; focus?: string }>()
  const { user } = useAuth()
  const { data: sessionData } = useCaseSession(sessionId)

  const [messages, setMessages] = useState<CaseMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [state, setState] = useState<CaseState | null>(null)
  const [showExamSheet, setShowExamSheet] = useState(false)
  const [showTestSheet, setShowTestSheet] = useState(false)
  const [ending, setEnding] = useState(false)
  const scrollViewRef = useRef<ScrollView>(null)
  const sessionLoadedRef = useRef(false)

  // 初始化：从 React Query 缓存加载会话状态
  useEffect(() => {
    if (sessionData && !sessionLoadedRef.current) {
      sessionLoadedRef.current = true
      setState({
        caseId: sessionData.case_id,
        sessionId: sessionData.id,
        currentPhase: sessionData.current_phase,
        revealed: sessionData.revealed || {
          historyFields: [],
          examPerformed: [],
          testsOrdered: [],
          testsResultsReleased: [],
        },
        turnCount: sessionData.turn_count || 0,
        hintsUsed: sessionData.hints_used || 0,
        maxHints: sessionData.max_hints || 3,
        startedAt: sessionData.started_at,
      })

      // 加载历史消息
      const loadMessages = async () => {
        try {
          const { data: msgs } = await supabase
            .from('case_messages')
            .select('*')
            .eq('session_id', sessionId!)
            .order('turn_number', { ascending: true })

          if (msgs) {
            setMessages(
              msgs.map((m) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                turnNumber: m.turn_number,
                intentType: m.intent_type,
                intentTarget: m.intent_target,
                createdAt: m.created_at,
              }))
            )
          }
        } catch (e) {
          console.error('加载消息失败:', e)
        }
      }
      loadMessages()
    }
  }, [sessionData, sessionId])

  const handleSend = async () => {
    if (!inputText.trim() || !user || !sessionId || loading) return

    const userMessage = inputText.trim()
    setInputText('')
    setLoading(true)

    // 立即显示用户消息
    const tempUserMsg: CaseMessage = {
      id: createLocalMessageId('temp'),
      role: 'user',
      content: userMessage,
      turnNumber: messages.length + 1,
      createdAt: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, tempUserMsg])

    try {
      const { response, state: newState, intent } = await caseEngine.handleMessage(
        sessionId,
        user.id,
        userMessage
      )

      setState(newState)

      // 添加助手回复
      const assistantMsg: CaseMessage = {
        id: createLocalMessageId('assistant'),
        role: 'assistant',
        content: response,
        turnNumber: messages.length + 1,
        intentType: intent.type,
        intentTarget: intent.target,
        createdAt: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch {
      Alert.alert('错误', '发送失败，请重试')
      // 移除临时消息
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id))
    } finally {
      setLoading(false)
    }
  }

  const handleExam = async (region: string) => {
    if (!user || !sessionId) return
    setShowExamSheet(false)

    // 模拟查体请求
    const message = `查${EXAM_REGIONS.find((r) => r.id === region)?.label || region}`
    setInputText('')
    await handleSendDirect(message)
  }

  const handleTest = async (testId: string) => {
    if (!user || !sessionId) return
    setShowTestSheet(false)

    const message = `做${LAB_TESTS.find((t) => t.id === testId)?.label || testId}`
    await handleSendDirect(message)
  }

  const handleSendDirect = async (message: string) => {
    if (!user || !sessionId || loading) return
    setLoading(true)

    const tempUserMsg: CaseMessage = {
      id: createLocalMessageId('temp'),
      role: 'user',
      content: message,
      turnNumber: messages.length + 1,
      createdAt: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, tempUserMsg])

    try {
      const { response, state: newState } = await caseEngine.handleMessage(sessionId, user.id, message)
      setState(newState)

      const assistantMsg: CaseMessage = {
        id: createLocalMessageId('assistant'),
        role: 'assistant',
        content: response,
        turnNumber: messages.length + 1,
        createdAt: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch {
      Alert.alert('错误', '操作失败')
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id))
    } finally {
      setLoading(false)
    }
  }

  const goToDiagnosis = () => {
    router.push(`/case/${sessionId}/diagnose`)
  }

  const handleHint = async () => {
    if (!user || !sessionId || loading || !state) return
    setLoading(true)
    try {
      const { hint, state: nextState } = await caseEngine.requestHint(
        sessionId,
        user.id,
      )
      setState(nextState)
      setMessages((previous) => [
        ...previous,
        {
          id: createLocalMessageId('hint'),
          role: 'system',
          content: hint,
          turnNumber: nextState.turnCount,
          createdAt: new Date().toISOString(),
        },
      ])
    } catch (error) {
      Alert.alert(
        '暂时无法获取提示',
        error instanceof Error ? error.message : '请稍后重试',
      )
    } finally {
      setLoading(false)
    }
  }

  const confirmAbandon = () => {
    if (!sessionId || ending) return
    Alert.alert(
      '结束本次病例？',
      '本次进度会标记为已放弃，不会计入完成病例。',
      [
        { text: '继续训练', style: 'cancel' },
        {
          text: '结束病例',
          style: 'destructive',
          onPress: async () => {
            setEnding(true)
            try {
              await abandonCase(sessionId)
              router.replace('/(tabs)/cases')
            } catch {
              Alert.alert('结束失败', '病例状态未改变，请稍后重试。')
              setEnding(false)
            }
          },
        },
      ],
    )
  }

  // 获取当前阶段的快捷操作
  const getQuickActions = () => {
    if (!state) return []
    switch (state.currentPhase) {
      case CasePhase.INTRO:
        return [
          { label: '开始问诊', action: () => setInputText('你好，请问你哪里不舒服？') },
        ]
      case CasePhase.HISTORY:
        return [
          { label: '查体', action: () => setShowExamSheet(true) },
          { label: '开检查', action: () => setShowTestSheet(true) },
        ]
      case CasePhase.EXAM:
        return [
          { label: '查体', action: () => setShowExamSheet(true) },
          { label: '开检查', action: () => setShowTestSheet(true) },
          { label: '提交诊断', action: goToDiagnosis },
        ]
      case CasePhase.TESTS:
        return [
          { label: '开检查', action: () => setShowTestSheet(true) },
          { label: '提交诊断', action: goToDiagnosis },
        ]
      default:
        return []
    }
  }

  const currentPhaseIndex = state
    ? [CasePhase.INTRO, CasePhase.HISTORY, CasePhase.EXAM, CasePhase.TESTS, CasePhase.DIAGNOSIS].indexOf(
        state.currentPhase
      )
    : 0

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      {/* Phase 指示器 */}
      {state && (
        <View style={styles.phaseBar}>
          {[CasePhase.HISTORY, CasePhase.EXAM, CasePhase.TESTS, CasePhase.DIAGNOSIS].map((phase, i) => {
            const isActive = state.currentPhase === phase
            const isPast = currentPhaseIndex > i + 1
            return (
              <View key={phase} style={styles.phaseItem}>
                <View
                  style={[
                    styles.phaseDot,
                    isActive && styles.phaseDotActive,
                    isPast && styles.phaseDotPast,
                  ]}
                >
                  <Text
                    style={[
                      styles.phaseDotText,
                      isActive && styles.phaseDotTextActive,
                      isPast && styles.phaseDotTextPast,
                    ]}
                  >
                    {isPast ? '✓' : i + 1}
                  </Text>
                </View>
                <Text style={[styles.phaseLabel, isActive && styles.phaseLabelActive]}>
                  {PHASE_LABELS[phase]}
                </Text>
              </View>
            )
          })}
        </View>
      )}

      {focus && (
        <View style={styles.focusBanner}>
          <Text style={styles.focusEyebrow}>本轮反馈目标</Text>
          <Text style={styles.focusText}>{focus}</Text>
        </View>
      )}

      {/* 消息列表 */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.messageList}
        contentContainerStyle={styles.messageListContent}
        onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
        keyboardDismissMode="on-drag"
      >
        {/* 系统消息 */}
        {messages.length === 0 && (
          <View style={styles.systemBubble}>
            <Text style={styles.systemText}>
              {'开始你的问诊吧！试着问患者"你今天怎么不舒服？"'}
            </Text>
          </View>
        )}

        {messages.map((msg) => (
          <View key={msg.id}>
            {msg.role === 'user' ? (
              <View style={styles.userBubbleContainer}>
                <View style={styles.userBubble}>
                  <Text style={styles.userText}>{msg.content}</Text>
                </View>
              </View>
            ) : (
              <View style={styles.assistantBubbleContainer}>
                <View style={styles.assistantBubble}>
                  <Text style={styles.assistantText}>{msg.content}</Text>
                </View>
              </View>
            )}
          </View>
        ))}

        {loading && (
          <View style={styles.assistantBubbleContainer}>
            <View style={styles.assistantBubble}>
              <View style={styles.typingIndicator}>
                <View style={[styles.typingDot, styles.typingDot1]} />
                <View style={[styles.typingDot, styles.typingDot2]} />
                <View style={[styles.typingDot, styles.typingDot3]} />
              </View>
            </View>
          </View>
        )}

        <View style={styles.chatDisclaimer}>
          <MedicalDisclaimer />
        </View>
      </ScrollView>

      {/* 快捷操作 */}
      {state && getQuickActions().length > 0 && (
        <View style={styles.quickActions}>
          {getQuickActions().map((action, i) => (
            <TouchableOpacity key={i} style={styles.quickActionBtn} onPress={action.action}>
              <Text style={styles.quickActionText}>{action.label}</Text>
            </TouchableOpacity>
          ))}
          <TouchableOpacity
            style={styles.hintActionBtn}
            onPress={handleHint}
            disabled={loading || state.hintsUsed >= state.maxHints}
          >
            <Text style={styles.hintActionText}>
              提示 {state.hintsUsed}/{state.maxHints}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* 输入框 */}
      <View style={styles.inputContainer}>
        <TouchableOpacity
          style={styles.endButton}
          onPress={confirmAbandon}
          disabled={ending}
        >
          {ending ? (
            <ActivityIndicator size="small" color={Colors.error} />
          ) : (
            <Ionicons name="stop-circle-outline" size={22} color={Colors.error} />
          )}
        </TouchableOpacity>
        <TextInput
          style={styles.textInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder="输入你的问题..."
          placeholderTextColor={Colors.textTertiary}
          multiline
          maxLength={500}
          editable={!loading}
        />
        <TouchableOpacity
          style={[styles.sendButton, (!inputText.trim() || loading) && styles.sendButtonDisabled]}
          onPress={handleSend}
          disabled={!inputText.trim() || loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.sendButtonText}>↑</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* 查体 Bottom Sheet */}
      {showExamSheet && (
        <>
          <TouchableOpacity
            style={styles.backdrop}
            activeOpacity={1}
            onPress={() => setShowExamSheet(false)}
          />
          <View style={styles.bottomSheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>选择查体区域</Text>
              <TouchableOpacity onPress={() => setShowExamSheet(false)}>
                <Ionicons name="close" size={19} color={Colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.sheetContent}>
              {EXAM_REGIONS.map((region) => {
                const done = state?.revealed.examPerformed.includes(region.id)
                return (
                  <TouchableOpacity
                    key={region.id}
                    style={[styles.sheetItem, done && styles.sheetItemDone]}
                    onPress={() => handleExam(region.id)}
                    disabled={done}
                  >
                    <View style={styles.sheetItemCopy}>
                      {done && <Ionicons name="checkmark-circle" size={17} color={Colors.success} />}
                      <Text style={[styles.sheetItemText, done && styles.sheetItemTextDone]}>
                        {region.label}
                      </Text>
                    </View>
                  </TouchableOpacity>
                )
              })}
            </ScrollView>
          </View>
        </>
      )}

      {/* 检查 Bottom Sheet */}
      {showTestSheet && (
        <>
          <TouchableOpacity
            style={styles.backdrop}
            activeOpacity={1}
            onPress={() => setShowTestSheet(false)}
          />
          <View style={styles.bottomSheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>选择检查项目</Text>
              <TouchableOpacity onPress={() => setShowTestSheet(false)}>
                <Ionicons name="close" size={19} color={Colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.sheetContent}>
              {LAB_TESTS.map((test) => {
                const done = state?.revealed.testsOrdered.includes(test.id)
                return (
                  <TouchableOpacity
                    key={test.id}
                    style={[styles.sheetItem, done && styles.sheetItemDone]}
                    onPress={() => handleTest(test.id)}
                    disabled={done}
                  >
                    <View style={styles.sheetItemCopy}>
                      {done && <Ionicons name="checkmark-circle" size={17} color={Colors.success} />}
                      <Text style={[styles.sheetItemText, done && styles.sheetItemTextDone]}>
                        {test.label}
                      </Text>
                    </View>
                  </TouchableOpacity>
                )
              })}
            </ScrollView>
          </View>
        </>
      )}
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  chatDisclaimer: {
    marginTop: Spacing.lg,
    marginBottom: Spacing.md,
    alignItems: 'center',
  },
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  focusBanner: {
    marginHorizontal: Spacing.base,
    marginTop: Spacing.sm,
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.primary[200],
    backgroundColor: Colors.primary[50],
  },
  focusEyebrow: {
    ...Typography.labelSmall,
    color: Colors.primary[700],
    fontWeight: '700',
    marginBottom: 3,
  },
  focusText: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
    lineHeight: 19,
  },
  // Phase 指示器
  phaseBar: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.surface,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  phaseItem: {
    alignItems: 'center',
    minWidth: 44,
  },
  phaseDot: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.neutral[200],
    alignItems: 'center',
    justifyContent: 'center',
  },
  phaseDotActive: {
    backgroundColor: Colors.primary[500],
  },
  phaseDotPast: {
    backgroundColor: Colors.primary[100],
  },
  phaseDotText: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
  },
  phaseDotTextActive: {
    color: '#fff',
  },
  phaseDotTextPast: {
    color: Colors.primary[500],
  },
  phaseLabel: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  phaseLabelActive: {
    color: Colors.primary[500],
    fontWeight: '600',
  },
  // 消息列表
  messageList: {
    flex: 1,
  },
  messageListContent: {
    padding: Spacing.md,
    paddingBottom: Spacing.xl,
  },
  systemBubble: {
    backgroundColor: Colors.neutral[100],
    padding: Spacing.md,
    borderRadius: BorderRadius.xl,
    alignSelf: 'center',
    marginVertical: Spacing.lg,
    maxWidth: '80%',
  },
  systemText: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  userBubbleContainer: {
    alignItems: 'flex-end',
    marginBottom: Spacing.sm,
    marginLeft: 60,
  },
  userBubble: {
    backgroundColor: Colors.primary[500],
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm,
    borderRadius: 16,
    borderBottomRightRadius: 4,
    maxWidth: '100%',
  },
  userText: {
    ...Typography.bodyMedium,
    color: '#fff',
  },
  assistantBubbleContainer: {
    alignItems: 'flex-start',
    marginBottom: Spacing.sm,
    marginRight: 60,
  },
  assistantBubble: {
    backgroundColor: Colors.surface,
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm,
    borderRadius: 16,
    borderBottomLeftRadius: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
    maxWidth: '100%',
  },
  assistantText: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    lineHeight: 22,
  },
  typingIndicator: {
    flexDirection: 'row',
    gap: 4,
    paddingVertical: 4,
  },
  typingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.neutral[300],
  },
  typingDot1: { opacity: 0.4 },
  typingDot2: { opacity: 0.7 },
  typingDot3: { opacity: 1 },
  // 快捷操作
  quickActions: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  quickActionBtn: {
    backgroundColor: Colors.primary[50],
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
  },
  quickActionText: {
    ...Typography.labelSmall,
    color: Colors.primary[500],
  },
  hintActionBtn: {
    marginLeft: 'auto',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  hintActionText: {
    ...Typography.labelSmall,
    color: Colors.textSecondary,
  },
  // 输入框
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: Spacing.md,
    backgroundColor: Colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
    gap: Spacing.sm,
  },
  endButton: {
    width: 36,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  textInput: {
    flex: 1,
    backgroundColor: Colors.neutral[100],
    borderRadius: 20,
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    maxHeight: 100,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: Colors.neutral[300],
  },
  sendButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  // Bottom Sheet
  backdrop: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    zIndex: 1,
  },
  bottomSheet: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: Colors.surface,
    borderTopLeftRadius: BorderRadius['2xl'],
    borderTopRightRadius: BorderRadius['2xl'],
    maxHeight: '60%',
    zIndex: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -8 },
    shadowOpacity: 0.2,
    shadowRadius: 24,
    elevation: 8,
  },
  sheetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  sheetTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  sheetClose: {
    fontSize: 20,
    color: Colors.textTertiary,
  },
  sheetContent: {
    padding: Spacing.md,
  },
  sheetItem: {
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.xs,
  },
  sheetItemCopy: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  sheetItemDone: {
    opacity: 0.5,
  },
  sheetItemText: {
    fontSize: 14,
    color: Colors.textPrimary,
  },
  sheetItemTextDone: {
    color: Colors.textTertiary,
  },
})

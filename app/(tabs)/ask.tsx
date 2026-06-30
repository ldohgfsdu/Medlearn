import { useState, useRef, useCallback, useEffect } from 'react'
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
  ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useRouter } from 'expo-router'
import { Colors, Typography, Spacing, BorderRadius, Shadows } from '@/constants/theme'
import { sendChatMessage } from '@/services/ai'
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

const QUICK_QUESTIONS = [
  { tag: '急症', question: '心肌梗死的典型症状有哪些？' },
  { tag: '鉴别', question: '如何鉴别肺炎和肺结核？' },
  { tag: '标准', question: '糖尿病的诊断标准是什么？' },
  { tag: '分级', question: '高血压的分级标准？' },
]

export default function AskScreen() {
  const router = useRouter()
  const [inputText, setInputText] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const scrollViewRef = useRef<ScrollView>(null)

  useEffect(() => {
    const showSubscription = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow',
      () => {
        setTimeout(() => scrollViewRef.current?.scrollToEnd({ animated: true }), 100)
      }
    )
    return () => showSubscription.remove()
  }, [])

  const handleSend = useCallback(async (text?: string) => {
    const question = text || inputText.trim()
    if (!question || isLoading) return

    setInputText('')
    setMessages(prev => [...prev, { id: `${Date.now()}-${Math.random()}`, role: 'user', content: question }])
    setIsLoading(true)

    try {
      const reply = await sendChatMessage([
        { role: 'user', content: question },
      ])
      setMessages(prev => [...prev, { id: `${Date.now()}-${Math.random()}`, role: 'assistant', content: reply }])
    } catch (e: any) {
      const msg = e?.message === 'AI_REQUEST_TIMEOUT'
        ? 'AI 响应较慢，请稍后再试或缩短问题。'
        : '抱歉，回答问题时出现了错误，请稍后重试。'
      setMessages(prev => [...prev, { id: `${Date.now()}-${Math.random()}`, role: 'assistant', content: msg }])
    } finally {
      setIsLoading(false)
    }
  }, [inputText, isLoading])

  const clearChat = useCallback(() => setMessages([]), [])

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      {messages.length === 0 ? (
        <ScrollView
          contentContainerStyle={styles.emptyContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.hero}>
            <View style={styles.heroTop}>
              <Text style={styles.heroIndex}>ASK / 01</Text>
              <View style={styles.aiMark}>
                <Ionicons name="sparkles-outline" size={22} color="#FFFDF9" />
              </View>
            </View>
            <Text style={styles.emptyTitle}>把问题问得{'\n'}具体一点</Text>
            <Text style={styles.emptySubtitle}>
              适合查概念、理清鉴别诊断、对比标准。回答会优先给出结构，而不是堆砌结论。
            </Text>
          </View>

          <View style={styles.notice}>
            <Ionicons name="information-circle-outline" size={18} color={Colors.primary[700]} />
            <Text style={styles.noticeText}>用于学习与复习，不替代临床判断或专业医疗建议。</Text>
          </View>

          <TouchableOpacity
            style={styles.immersiveLink}
            activeOpacity={0.7}
            onPress={() => router.push('/ai-chat')}
          >
            <View>
              <Text style={styles.immersiveEyebrow}>CONVERSATION MODE</Text>
              <Text style={styles.immersiveTitle}>进入沉浸式连续对话</Text>
            </View>
            <Ionicons name="arrow-forward" size={18} color="#FFFDF9" />
          </TouchableOpacity>

          <View style={styles.sectionHeader}>
            <View>
              <Text style={styles.sectionEyebrow}>STARTING POINTS</Text>
              <Text style={styles.sectionTitle}>可以这样问</Text>
            </View>
            <Text style={styles.sectionCount}>04</Text>
          </View>

          <View style={styles.quickList}>
            {QUICK_QUESTIONS.map((item, index) => (
              <TouchableOpacity
                key={item.question}
                style={[styles.quickRow, index < QUICK_QUESTIONS.length - 1 && styles.quickRowBorder]}
                onPress={() => handleSend(item.question)}
                activeOpacity={0.65}
              >
                <Text style={styles.quickIndex}>{String(index + 1).padStart(2, '0')}</Text>
                <View style={styles.quickCopy}>
                  <Text style={styles.quickTag}>{item.tag}</Text>
                  <Text style={styles.quickQuestion}>{item.question}</Text>
                </View>
                <Ionicons name="arrow-up-outline" size={17} color={Colors.primary[700]} />
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      ) : (
        <ScrollView
          ref={scrollViewRef}
          style={styles.messageList}
          contentContainerStyle={styles.messageListContent}
          showsVerticalScrollIndicator={false}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: false })}
        >
          <View style={styles.conversationHeader}>
            <View>
              <Text style={styles.conversationEyebrow}>MEDICAL Q&A</Text>
              <Text style={styles.conversationTitle}>学习问答</Text>
            </View>
            <TouchableOpacity style={styles.clearButton} onPress={clearChat}>
              <Ionicons name="close" size={18} color={Colors.textSecondary} />
            </TouchableOpacity>
          </View>

          {messages.map((message, index) => (
            <View
              key={message.id}
              style={[
                styles.messageBlock,
                message.role === 'user' ? styles.userBlock : styles.assistantBlock,
              ]}
            >
              <View style={styles.messageMeta}>
                <Text style={[
                  styles.messageRole,
                  message.role === 'user' ? styles.userRole : styles.assistantRole,
                ]}>
                  {message.role === 'user' ? 'YOU' : 'MEDLEARN AI'}
                </Text>
                <Text style={[
                  styles.messageNumber,
                  message.role === 'user' ? styles.userRole : styles.assistantRole,
                ]}>
                  {String(index + 1).padStart(2, '0')}
                </Text>
              </View>
              <Text style={[
                styles.messageText,
                message.role === 'user' ? styles.userText : styles.assistantText,
              ]}>
                {message.content}
              </Text>
            </View>
          ))}

          {isLoading && (
            <View style={[styles.messageBlock, styles.assistantBlock]}>
              <View style={styles.messageMeta}>
                <Text style={[styles.messageRole, styles.assistantRole]}>MEDLEARN AI</Text>
                <Ionicons name="ellipsis-horizontal" size={18} color={Colors.primary[700]} />
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <ActivityIndicator size="small" color={Colors.primary[700]} />
                <Text style={[styles.messageText, styles.assistantText]}>正在整理回答...</Text>
              </View>
            </View>
          )}

          {messages.length > 0 && (
            <View style={styles.disclaimerWrap}>
              <MedicalDisclaimer />
            </View>
          )}
        </ScrollView>
      )}

      <View style={styles.inputWrapper}>
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.textInput}
            value={inputText}
            onChangeText={setInputText}
            placeholder="输入一个具体的医学问题"
            placeholderTextColor={Colors.textTertiary}
            multiline
            maxLength={500}
            editable={!isLoading}
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!inputText.trim() || isLoading) && styles.sendBtnDisabled]}
            onPress={() => handleSend()}
            disabled={!inputText.trim() || isLoading}
          >
            <Ionicons
              name="arrow-up"
              size={19}
              color={inputText.trim() && !isLoading ? '#FFFDF9' : Colors.textTertiary}
            />
          </TouchableOpacity>
        </View>
        <Text style={styles.inputHint}>建议包含人群、时间、症状或需要对比的对象</Text>
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  emptyContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xl,
  },
  hero: {
    minHeight: 248,
    backgroundColor: '#E7DCC9',
    borderRadius: BorderRadius['2xl'],
    padding: Spacing.xl,
    marginBottom: Spacing.md,
    overflow: 'hidden',
  },
  heroTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heroIndex: {
    fontSize: 10,
    lineHeight: 14,
    fontWeight: '800',
    letterSpacing: 1.4,
    color: Colors.primary[700],
  },
  aiMark: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.ink,
  },
  emptyTitle: {
    fontSize: 34,
    lineHeight: 42,
    fontWeight: '800',
    letterSpacing: -1,
    color: Colors.textPrimary,
    marginTop: Spacing.lg,
  },
  emptySubtitle: {
    ...Typography.bodyMedium,
    lineHeight: 22,
    color: Colors.textSecondary,
    marginTop: Spacing.md,
    maxWidth: 330,
  },
  notice: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    marginBottom: Spacing.xl,
  },
  noticeText: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    flex: 1,
  },
  immersiveLink: {
    minHeight: 64,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    marginBottom: Spacing.xl,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.ink,
  },
  immersiveEyebrow: {
    fontSize: 8,
    lineHeight: 12,
    fontWeight: '800',
    letterSpacing: 1.3,
    color: '#9DC8B9',
    marginBottom: 2,
  },
  immersiveTitle: {
    ...Typography.titleSmall,
    color: '#FFFDF9',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  sectionEyebrow: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '700',
    letterSpacing: 1.4,
    color: Colors.textTertiary,
    marginBottom: 3,
  },
  sectionTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  sectionCount: {
    fontSize: 13,
    color: Colors.textTertiary,
  },
  quickList: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.base,
  },
  quickRow: {
    minHeight: 78,
    flexDirection: 'row',
    alignItems: 'center',
  },
  quickRowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  quickIndex: {
    width: 30,
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textTertiary,
  },
  quickCopy: {
    flex: 1,
    paddingRight: Spacing.md,
  },
  quickTag: {
    fontSize: 9,
    lineHeight: 12,
    fontWeight: '700',
    letterSpacing: 1,
    color: Colors.primary[700],
    marginBottom: 3,
  },
  quickQuestion: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  messageList: {
    flex: 1,
  },
  messageListContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xl,
  },
  conversationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.xl,
  },
  conversationEyebrow: {
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 1.4,
    color: Colors.textTertiary,
    marginBottom: 3,
  },
  conversationTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  clearButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  messageBlock: {
    width: '92%',
    padding: Spacing.lg,
    borderRadius: BorderRadius.xl,
    marginBottom: Spacing.md,
  },
  userBlock: {
    alignSelf: 'flex-end',
    backgroundColor: Colors.ink,
  },
  assistantBlock: {
    alignSelf: 'flex-start',
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  messageMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  messageRole: {
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1.2,
  },
  messageNumber: {
    fontSize: 10,
    fontWeight: '700',
  },
  userRole: {
    color: '#9DC8B9',
  },
  assistantRole: {
    color: Colors.primary[700],
  },
  messageText: {
    ...Typography.bodyMedium,
    lineHeight: 23,
  },
  userText: {
    color: '#FFFDF9',
  },
  assistantText: {
    color: Colors.textPrimary,
  },
  inputWrapper: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.md,
    backgroundColor: Colors.background,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius['2xl'],
    borderWidth: 1,
    borderColor: Colors.border,
    paddingLeft: Spacing.base,
    paddingRight: Spacing.sm,
    paddingVertical: Spacing.sm,
    ...Shadows.level1,
  },
  textInput: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    maxHeight: 100,
    minHeight: 38,
    paddingVertical: Spacing.sm,
    paddingRight: Spacing.sm,
  },
  sendBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: Colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: Colors.neutral[200],
  },
  inputHint: {
    fontSize: 9,
    lineHeight: 13,
    color: Colors.textTertiary,
    textAlign: 'center',
    marginTop: Spacing.xs,
  },
  disclaimerWrap: {
    marginTop: Spacing.md,
    marginBottom: Spacing.lg,
    alignItems: 'center',
  },
})

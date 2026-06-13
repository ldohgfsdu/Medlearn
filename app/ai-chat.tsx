import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Animated,
  PanResponder,
  Dimensions,
  StatusBar,
  Keyboard,
  ActivityIndicator,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useRouter } from 'expo-router'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Colors, Typography, Spacing, BorderRadius, Shadows } from '@/constants/theme'
import { sendChatMessage } from '@/services/ai'
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer'

const { width: SCREEN_WIDTH } = Dimensions.get('window')
const DRAWER_WIDTH = SCREEN_WIDTH * 0.75

interface Conversation {
  id: string
  title: string
  date: string
}

const MOCK_CONVERSATIONS: Conversation[] = [
  { id: '1', title: '新对话', date: '今天' },
  { id: '2', title: '心肌梗死病例讨论', date: '昨天' },
  { id: '3', title: '糖尿病诊断标准', date: '昨天' },
  { id: '4', title: '肺炎 vs 肺结核鉴别', date: '前天' },
]

export default function AIChatScreen() {
  const router = useRouter()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [inputText, setInputText] = useState('')
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [conversations] = useState<Conversation[]>(MOCK_CONVERSATIONS)
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null)
  const [voiceMode, setVoiceMode] = useState(false)

  // 动画值
  const [translateX] = useState(() => new Animated.Value(0))
  const [scale] = useState(() => new Animated.Value(1))
  const [borderRadius] = useState(() => new Animated.Value(0))
  const [overlayOpacity] = useState(() => new Animated.Value(0))
  const scrollViewRef = useRef<ScrollView>(null)

  const animateDrawer = useCallback((open: boolean) => {
    setDrawerOpen(open)
    Animated.parallel([
      Animated.timing(translateX, {
        toValue: open ? DRAWER_WIDTH : 0,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.timing(scale, {
        toValue: open ? 0.92 : 1,
        duration: 300,
        useNativeDriver: true,
      }),
      Animated.timing(borderRadius, {
        toValue: open ? 24 : 0,
        duration: 300,
        useNativeDriver: false,
      }),
      Animated.timing(overlayOpacity, {
        toValue: open ? 0.5 : 0,
        duration: 300,
        useNativeDriver: true,
      }),
    ]).start()
  }, [translateX, scale, borderRadius, overlayOpacity])

  const panResponder = useMemo(
    () => PanResponder.create({
      onMoveShouldSetPanResponder: (_, gestureState) => {
        if (!drawerOpen && gestureState.moveX > 40) return false
        return Math.abs(gestureState.dx) > 10
      },
      onPanResponderMove: (_, gestureState) => {
        if (drawerOpen) {
          if (gestureState.dx < 0) {
            const newX = Math.max(0, DRAWER_WIDTH + gestureState.dx)
            translateX.setValue(newX)
            scale.setValue(0.92 + (newX / DRAWER_WIDTH) * 0.08)
            overlayOpacity.setValue((newX / DRAWER_WIDTH) * 0.5)
          }
        } else {
          if (gestureState.dx > 0) {
            const newX = Math.min(DRAWER_WIDTH, gestureState.dx)
            translateX.setValue(newX)
            scale.setValue(1 - (newX / DRAWER_WIDTH) * 0.08)
            overlayOpacity.setValue((newX / DRAWER_WIDTH) * 0.5)
          }
        }
      },
      onPanResponderRelease: (_, gestureState) => {
        if (drawerOpen) {
          if (gestureState.dx < -DRAWER_WIDTH * 0.2) {
            animateDrawer(false)
          } else {
            animateDrawer(true)
          }
        } else {
          if (gestureState.dx > DRAWER_WIDTH * 0.2) {
            animateDrawer(true)
          } else {
            animateDrawer(false)
          }
        }
      },
    }),
    [animateDrawer, drawerOpen, overlayOpacity, scale, translateX]
  )

  // 键盘弹出时自动滚动到底部
  useEffect(() => {
    const showSubscription = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow',
      () => {
        setTimeout(() => {
          scrollViewRef.current?.scrollToEnd({ animated: true })
        }, 100)
      }
    )
    return () => showSubscription.remove()
  }, [])

  const [sending, setSending] = useState(false)

  const handleSend = async () => {
    if (!inputText.trim() || sending) return
    const userMessage = inputText.trim()
    setInputText('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setSending(true)

    try {
      const reply = await sendChatMessage([{ role: 'user', content: userMessage }])
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }])
    } catch (e: any) {
      const msg = e?.message === 'AI_REQUEST_TIMEOUT'
        ? 'AI 响应较慢，请稍后再试。'
        : '抱歉，暂时无法获取回答，请稍后重试。'
      setMessages((prev) => [...prev, { role: 'assistant', content: msg }])
    } finally {
      setSending(false)
    }
  }

  const startNewChat = () => {
    setMessages([])
    setActiveConversation(null)
    animateDrawer(false)
  }

  const selectConversation = (conv: Conversation) => {
    setActiveConversation(conv)
    setMessages([
      { role: 'assistant', content: `已打开「${conv.title}」。你可以继续追问，或补充新的病例信息。` },
    ])
    animateDrawer(false)
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={drawerOpen ? '#000' : Colors.background} />

      {/* 抽屉层 */}
      <View style={styles.drawerContainer}>
        <View style={styles.drawerHeader}>
          <Text style={styles.drawerTitle}>会话</Text>
          <TouchableOpacity style={styles.newChatBtn} onPress={startNewChat}>
            <Ionicons name="create-outline" size={20} color={Colors.textSecondary} />
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.drawerContent} showsVerticalScrollIndicator={false}>
          <Text style={styles.dateLabel}>今天</Text>
          {conversations.map((conv) => (
            <TouchableOpacity
              key={conv.id}
              style={styles.conversationItem}
              onPress={() => selectConversation(conv)}
            >
              <Text style={styles.conversationTitle}>{conv.title}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        <TouchableOpacity style={styles.drawerBack} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={17} color={Colors.textSecondary} />
          <Text style={styles.drawerBackText}>返回智能问答</Text>
        </TouchableOpacity>
      </View>

      {/* 主内容层 */}
      <Animated.View
        style={[
          styles.mainContainer,
          {
            transform: [
              { translateX },
              { scale },
            ],
            borderRadius,
          },
        ]}
        {...panResponder.panHandlers}
      >
        <KeyboardAvoidingView
          style={styles.keyboardView}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 24}
        >
          {/* 顶部导航栏 */}
          <View style={styles.header}>
            <TouchableOpacity style={styles.headerBtn} onPress={() => animateDrawer(!drawerOpen)}>
              <Ionicons name="menu" size={22} color={Colors.textPrimary} />
            </TouchableOpacity>

            <Text style={styles.headerTitle} numberOfLines={1}>
              {activeConversation?.title || '智能助手'}
            </Text>

            <View style={styles.headerRight}>
              <TouchableOpacity
                style={[styles.headerBtn, voiceMode && styles.headerBtnActive]}
                onPress={() => setVoiceMode(enabled => !enabled)}
              >
                <Ionicons
                  name={voiceMode ? 'headset' : 'headset-outline'}
                  size={22}
                  color={voiceMode ? Colors.primary[700] : Colors.textPrimary}
                />
              </TouchableOpacity>
              <TouchableOpacity style={styles.headerBtn} onPress={startNewChat}>
                <Ionicons name="add" size={22} color={Colors.textPrimary} />
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.headerBtn}
                onPress={() => router.push('/(tabs)/profile')}
              >
                <Ionicons name="settings-outline" size={22} color={Colors.textPrimary} />
              </TouchableOpacity>
            </View>
          </View>

          {/* 消息区域 */}
          {messages.length === 0 ? (
            <View style={styles.emptyState}>
              <View style={styles.lightningContainer}>
                <Ionicons name="flash" size={32} color={Colors.textPrimary} />
              </View>
              <Text style={styles.emptyTitle}>接下来想聊点什么？</Text>
            </View>
          ) : (
            <ScrollView
              ref={scrollViewRef}
              style={styles.messageList}
              contentContainerStyle={styles.messageListContent}
              showsVerticalScrollIndicator={false}
              onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: false })}
            >
              {messages.map((msg, index) => (
                <View
                  key={index}
                  style={[
                    styles.messageBubble,
                    msg.role === 'user' ? styles.userBubble : styles.assistantBubble,
                  ]}
                >
                  <Text
                    style={[
                      styles.messageText,
                      msg.role === 'user' ? styles.userText : styles.assistantText,
                    ]}
                  >
                    {msg.content}
                  </Text>
                </View>
              ))}
            </ScrollView>
          )}

          {messages.length > 0 && (
            <View style={styles.disclaimerContainer}>
              <MedicalDisclaimer />
            </View>
          )}

          {/* 底部输入框 */}
          <View style={styles.inputWrapper}>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.textInput}
                value={inputText}
                onChangeText={setInputText}
                placeholder="问我任何问题..."
                placeholderTextColor={Colors.textTertiary}
                multiline
                maxLength={500}
              />
              <TouchableOpacity
                style={[styles.sendBtn, (!inputText.trim() || sending) && styles.sendBtnDisabled]}
                onPress={handleSend}
                disabled={!inputText.trim() || sending}
              >
                {sending ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Ionicons name="arrow-up" size={20} color={inputText.trim() ? '#fff' : Colors.textTertiary} />
                )}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>

        {/* 遮罩层 — 始终挂载，靠 opacity 控制显隐 */}
        <Animated.View style={[styles.overlay, { opacity: overlayOpacity }]}>
          <TouchableOpacity
            style={styles.overlayTouchable}
            activeOpacity={1}
            onPress={() => animateDrawer(false)}
          />
        </Animated.View>
      </Animated.View>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  drawerContainer: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    width: DRAWER_WIDTH,
    backgroundColor: Colors.background,
    paddingTop: Spacing.lg,
    paddingHorizontal: Spacing.md,
  },
  drawerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.lg,
    paddingHorizontal: Spacing.sm,
  },
  drawerTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  newChatBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.neutral[100],
    alignItems: 'center',
    justifyContent: 'center',
  },
  drawerContent: {
    flex: 1,
  },
  drawerBack: {
    minHeight: 46,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  drawerBackText: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
  },
  dateLabel: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
    paddingHorizontal: Spacing.sm,
  },
  conversationItem: {
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.base,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.xs,
    backgroundColor: Colors.neutral[100],
  },
  conversationTitle: {
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    fontWeight: '500',
  },
  mainContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    overflow: 'hidden',
    ...Shadows.level3,
  },
  keyboardView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.background,
  },
  headerBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.neutral[100],
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: 2,
  },
  headerTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
    fontWeight: '700',
    flex: 1,
    marginLeft: Spacing.md,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerBtnActive: {
    backgroundColor: Colors.primary[50],
  },
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingBottom: 100,
  },
  lightningContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.neutral[100],
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.lg,
  },
  emptyTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  messageList: {
    flex: 1,
  },
  messageListContent: {
    padding: Spacing.md,
    paddingBottom: Spacing.xl,
  },
  messageBubble: {
    maxWidth: '80%',
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.xl,
    marginBottom: Spacing.sm,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: Colors.primary[500],
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: Colors.surface,
    borderBottomLeftRadius: 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
  },
  messageText: {
    ...Typography.bodyMedium,
    lineHeight: 22,
  },
  userText: {
    color: '#fff',
  },
  assistantText: {
    color: Colors.textPrimary,
  },
  inputWrapper: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    backgroundColor: Colors.background,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius['2xl'],
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm,
    ...Shadows.level2,
  },
  textInput: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    maxHeight: 100,
    paddingVertical: Spacing.sm,
    paddingRight: Spacing.sm,
  },
  sendBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.textPrimary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: Colors.neutral[200],
  },
  overlay: {
    position: 'absolute',
    inset: 0,
    backgroundColor: '#000',
    pointerEvents: 'box-none',
  },
  overlayTouchable: {
    flex: 1,
  },
  disclaimerContainer: {
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.sm,
  },
})

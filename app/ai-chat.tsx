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
import { Colors, Typography, Spacing, BorderRadius } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { sendChatMessage } from '@/services/ai'
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer'

const { width: SCREEN_WIDTH } = Dimensions.get('window')
const DRAWER_WIDTH = SCREEN_WIDTH * 0.75

export default function AIChatScreen() {
  const router = useRouter()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [inputText, setInputText] = useState('')
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])

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
    animateDrawer(false)
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.background} />

      <View style={styles.drawerContainer}>
        <View style={styles.drawerHeader}>
          <Text style={styles.drawerTitle}>会话</Text>
          <TouchableOpacity style={styles.newChatBtn} onPress={startNewChat}>
            <Ionicons name="create-outline" size={20} color={Colors.textSecondary} />
          </TouchableOpacity>
        </View>

        <View style={styles.drawerEmpty}>
          <Ionicons name="chatbubbles-outline" size={32} color={Colors.neutral[300]} />
          <Text style={styles.drawerEmptyTitle}>暂无历史会话</Text>
          <Text style={styles.drawerEmptyText}>会话记录功能即将上线，当前可开始新对话。</Text>
        </View>

        <TouchableOpacity style={styles.drawerBack} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={17} color={Colors.textSecondary} />
          <Text style={styles.drawerBackText}>返回学习问答</Text>
        </TouchableOpacity>
      </View>

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
          <View style={styles.header}>
            <TouchableOpacity style={styles.headerBtn} onPress={() => animateDrawer(!drawerOpen)}>
              <Ionicons name="menu" size={22} color={Colors.textPrimary} />
            </TouchableOpacity>

            <Text style={styles.headerTitle} numberOfLines={1}>
              学习问答
            </Text>

            <View style={styles.headerRight}>
              <TouchableOpacity style={styles.headerBtn} onPress={startNewChat}>
                <Ionicons name="add" size={22} color={Colors.textPrimary} />
              </TouchableOpacity>
            </View>
          </View>

          {messages.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>输入一个具体的医学问题</Text>
              <Text style={styles.emptySubtitle}>回答会优先给出结构，便于复习与对照。</Text>
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

          <View style={styles.inputWrapper}>
            <View style={styles.inputContainer}>
              <TextInput
                style={styles.textInput}
                value={inputText}
                onChangeText={setInputText}
                placeholder="输入医学问题..."
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
                  <ActivityIndicator color={Colors.surface} size="small" />
                ) : (
                  <Ionicons
                    name="arrow-up"
                    size={20}
                    color={inputText.trim() ? Colors.surface : Colors.textTertiary}
                  />
                )}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>

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
    backgroundColor: Colors.background,
  },
  drawerContainer: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    width: DRAWER_WIDTH,
    backgroundColor: Colors.background,
    paddingTop: Spacing.lg,
    paddingHorizontal: Layout.screenPaddingX,
  },
  drawerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  drawerTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  newChatBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.neutral[100],
    alignItems: 'center',
    justifyContent: 'center',
  },
  drawerEmpty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.lg,
  },
  drawerEmptyTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
    marginTop: Spacing.md,
    fontWeight: '600',
  },
  drawerEmptyText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    textAlign: 'center',
    marginTop: Spacing.sm,
    lineHeight: 20,
  },
  drawerBack: {
    minHeight: 48,
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
  mainContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    overflow: 'hidden',
  },
  keyboardView: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Layout.screenPaddingX,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.background,
  },
  headerBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
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
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: 100,
  },
  emptyTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
    fontWeight: '600',
    textAlign: 'center',
  },
  emptySubtitle: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginTop: Spacing.sm,
    lineHeight: 24,
  },
  messageList: {
    flex: 1,
  },
  messageListContent: {
    padding: Layout.screenPaddingX,
    paddingBottom: Spacing.xl,
  },
  messageBubble: {
    maxWidth: '80%',
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm,
    borderRadius: Layout.cardRadius,
    marginBottom: Spacing.sm,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: Colors.primary[700],
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
    lineHeight: 24,
  },
  userText: {
    color: Colors.surface,
  },
  assistantText: {
    color: Colors.textPrimary,
  },
  inputWrapper: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingVertical: Spacing.md,
    backgroundColor: Colors.background,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius['2xl'],
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.sm,
  },
  textInput: {
    flex: 1,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    maxHeight: 100,
    minHeight: 44,
    paddingVertical: Spacing.sm,
    paddingRight: Spacing.sm,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.primary[700],
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: Colors.neutral[200],
  },
  overlay: {
    position: 'absolute',
    inset: 0,
    backgroundColor: Colors.ink,
  },
  overlayTouchable: {
    flex: 1,
  },
  disclaimerContainer: {
    alignItems: 'center',
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Spacing.sm,
  },
})
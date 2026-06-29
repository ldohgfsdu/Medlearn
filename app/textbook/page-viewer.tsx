import { useMemo } from 'react'
import {
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  useWindowDimensions,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Stack, useLocalSearchParams, useRouter } from 'expo-router'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { PageViewerHighlightOverlay } from '@/components/textbook/PageViewerHighlightOverlay'
import { BorderRadius, Colors, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { buildPageViewerPayload } from '@/services/phase1VisualEvidenceService'

export default function TextbookPageViewerScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { width: windowWidth } = useWindowDimensions()
  const { locatorIds = '', pageLabel = '', sectionId = '' } = useLocalSearchParams<{
    locatorIds?: string
    pageLabel?: string
    sectionId?: string
  }>()

  const ids = useMemo(
    () => locatorIds.split(',').map((s) => s.trim()).filter(Boolean),
    [locatorIds],
  )

  const payload = useMemo(
    () => buildPageViewerPayload(ids, pageLabel || undefined),
    [ids, pageLabel],
  )

  const displayWidth = windowWidth - Layout.screenPaddingX * 2
  const aspect = payload ? payload.imageHeight / payload.imageWidth : 1.4
  const displayHeight = displayWidth * aspect

  return (
    <View style={styles.screen}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={[styles.topBar, { paddingTop: insets.top + Spacing.xs }]}>
        <TouchableOpacity style={styles.iconButton} onPress={() => router.back()} activeOpacity={0.7}>
          <Ionicons name="arrow-back" size={25} color={Colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.topCopy}>
          <Text style={styles.topTitle} numberOfLines={1}>
            教材原文
          </Text>
          {payload ? (
            <Text style={styles.topMeta} numberOfLines={1}>
              {payload.textbookTitle} · P{payload.pageLabel}
            </Text>
          ) : null}
        </View>
      </View>

      {!payload ? (
        <View style={styles.stateBlock}>
          <Ionicons name="document-outline" size={32} color={Colors.neutral[300]} />
          <Text style={styles.stateTitle}>无法打开教材页图</Text>
          <Text style={styles.stateText}>
            定位数据或页图资源缺失。section={sectionId || '—'}
          </Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator
          maximumZoomScale={3}
          minimumZoomScale={1}
        >
          <View style={[styles.pageFrame, { width: displayWidth, height: displayHeight }]}>
            <Image
              source={payload.imageSource}
              style={{ width: displayWidth, height: displayHeight }}
              resizeMode="contain"
              accessibilityLabel={`教材第 ${payload.pageLabel} 页`}
            />
            <PageViewerHighlightOverlay
              locators={payload.locators}
              layoutWidth={displayWidth}
              layoutHeight={displayHeight}
            />
          </View>
          <Text style={styles.caption}>
            荧光笔高亮为当前证据在教材中的位置（共 {payload.locators.length} 处）
          </Text>
        </ScrollView>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  topBar: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Spacing.xs,
    backgroundColor: Colors.background,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  iconButton: {
    width: 44,
    minHeight: 44,
    alignItems: 'flex-start',
    justifyContent: 'center',
  },
  topCopy: {
    flex: 1,
  },
  topTitle: {
    fontSize: 20,
    lineHeight: 26,
    color: Colors.textPrimary,
    fontWeight: '800',
  },
  topMeta: {
    ...Typography.labelMedium,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  scrollContent: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingVertical: Spacing.md,
    paddingBottom: Layout.screenPaddingBottom,
  },
  pageFrame: {
    alignSelf: 'center',
    position: 'relative',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    overflow: 'hidden',
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
  },
  caption: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    textAlign: 'center',
    marginTop: Spacing.md,
  },
  stateBlock: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl,
    gap: Spacing.sm,
  },
  stateTitle: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  stateText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    textAlign: 'center',
  },
})
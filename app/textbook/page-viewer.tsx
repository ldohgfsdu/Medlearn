import { useMemo, useRef, useState } from 'react'
import {
  Image,
  ImageSourcePropType,
  Modal,
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
import { BorderRadius, Colors, FontFamily, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'
import { buildPageViewerPayload } from '@/services/phase1VisualEvidenceService'
import { formatTextbookPageReference } from '@/services/textbookService'

// 缩放档位：1x 适合纵览整页，2.5x 适合阅读段落正文。
const ZOOM_FIT = 1
const ZOOM_READ = 2.5

/**
 * 全屏页图查看器，支持双击切换缩放档位。
 * Pinch-zoom 在 Android RN 跨 ScrollView.maximumZoomScale / PanResponder /
 * gesture-handler 不可靠（后者需要本项目未配置的 reanimated babel 插件），
 * 因此用双击切换 1x ↔ 2.5x + ScrollView 拖拽查看，作为可靠跨平台方案。
 */
function FullscreenImage({
  source,
  imageWidth,
  imageHeight,
  viewportHeight,
  locators,
}: {
  source: ImageSourcePropType
  imageWidth: number
  imageHeight: number
  viewportHeight: number
  locators: NonNullable<ReturnType<typeof buildPageViewerPayload>>['locators']
}) {
  const [zoom, setZoom] = useState(ZOOM_FIT)
  const lastTapRef = useRef(0)

  const handleDoubleTap = () => {
    const now = Date.now()
    if (now - lastTapRef.current < 300) {
      setZoom((z) => (z === ZOOM_FIT ? ZOOM_READ : ZOOM_FIT))
      lastTapRef.current = 0
    } else {
      lastTapRef.current = now
    }
  }

  const scaledWidth = imageWidth * zoom
  const scaledHeight = imageHeight * zoom

  return (
    <View style={fullscreenStyles.fill}>
      <ScrollView
        horizontal
        nestedScrollEnabled
        contentContainerStyle={fullscreenStyles.horizontalScrollContent}
        showsHorizontalScrollIndicator={false}
      >
        <ScrollView
          nestedScrollEnabled
          style={{ width: scaledWidth, height: viewportHeight }}
          contentContainerStyle={fullscreenStyles.verticalScrollContent}
          showsVerticalScrollIndicator={false}
        >
          <TouchableOpacity
            activeOpacity={1}
            onPress={handleDoubleTap}
            accessibilityRole="button"
            accessibilityLabel={zoom === ZOOM_FIT ? '双击放大教材页图' : '双击缩小教材页图'}
            accessibilityHint="放大后可上下左右拖动查看教材正文"
          >
            <View style={{ width: scaledWidth, height: scaledHeight, position: 'relative' }}>
              <Image
                source={source}
                style={{ width: scaledWidth, height: scaledHeight }}
                resizeMode="contain"
              />
              <PageViewerHighlightOverlay
                locators={locators}
                layoutWidth={scaledWidth}
                layoutHeight={scaledHeight}
              />
            </View>
          </TouchableOpacity>
        </ScrollView>
      </ScrollView>
      <View style={fullscreenStyles.zoomHint}>
        <Text style={fullscreenStyles.zoomHintText}>
          {zoom === ZOOM_FIT ? '双击放大' : '双击缩小'} · {zoom}x
        </Text>
      </View>
    </View>
  )
}

const fullscreenStyles = StyleSheet.create({
  fill: {
    flex: 1,
    backgroundColor: '#000',
  },
  horizontalScrollContent: {
    minWidth: '100%',
    alignItems: 'center',
  },
  verticalScrollContent: {
    minHeight: '100%',
    justifyContent: 'center',
  },
  zoomHint: {
    position: 'absolute',
    bottom: Spacing['2xl'],
    alignSelf: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  zoomHintText: {
    ...Typography.labelSmall,
    color: '#fff',
  },
})

export default function TextbookPageViewerScreen() {
  const router = useRouter()
  const insets = useSafeAreaInsets()
  const { width: windowWidth, height: windowHeight } = useWindowDimensions()
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
  const fullscreenFitWidth = Math.min(windowWidth, windowHeight / aspect)
  const fullscreenFitHeight = fullscreenFitWidth * aspect

  const [fullscreen, setFullscreen] = useState(false)

  return (
    <View style={styles.screen}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={[styles.topBar, { paddingTop: insets.top + Spacing.xs }]}>
        <TouchableOpacity
          style={styles.iconButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="返回教材内容"
        >
          <Ionicons name="arrow-back" size={25} color={Colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.topCopy}>
          <Text style={styles.topTitle} numberOfLines={1}>
            教材原文
          </Text>
          {payload ? (
            <Text style={styles.topMeta} numberOfLines={1}>
              {payload.textbookTitle} · {formatTextbookPageReference(payload.pageLabel, 'printed')}
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
        >
          <TouchableOpacity
            activeOpacity={0.9}
            onPress={() => setFullscreen(true)}
            accessibilityRole="button"
            accessibilityLabel="点击全屏查看教材页图"
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
          </TouchableOpacity>
          <Text style={styles.caption}>
            荧光笔高亮为当前证据在教材中的位置（共 {payload.locators.length} 处）· 点击图片全屏查看 · 全屏内双击放大
          </Text>
        </ScrollView>
      )}

      <Modal visible={fullscreen} animationType="fade" transparent onRequestClose={() => setFullscreen(false)}>
        <View style={styles.modalRoot}>
          {payload ? (
            <FullscreenImage
              source={payload.imageSource}
              imageWidth={fullscreenFitWidth}
              imageHeight={fullscreenFitHeight}
              viewportHeight={windowHeight}
              locators={payload.locators}
            />
          ) : null}
          <TouchableOpacity
            style={[styles.modalClose, { top: insets.top + Spacing.xs }]}
            onPress={() => setFullscreen(false)}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel="关闭全屏查看"
          >
            <Ionicons name="close" size={26} color="#fff" />
          </TouchableOpacity>
        </View>
      </Modal>
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
    fontWeight: '600',
    fontFamily: FontFamily.serif,
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
  modalRoot: {
    flex: 1,
    backgroundColor: '#000',
  },
  modalClose: {
    position: 'absolute',
    right: Layout.screenPaddingX,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(0,0,0,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
  },
})

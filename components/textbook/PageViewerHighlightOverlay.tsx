import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native'
import type { Phase1SourceLocator } from '@/constants/phase1VisualEvidenceBundle'

/** Marker-style highlight (runtime only — never baked into webp). */
export const PHASE1_HIGHLIGHT_STYLE = {
  backgroundColor: 'rgba(255, 230, 80, 0.45)',
  borderColor: 'rgba(230, 180, 0, 0.35)',
  borderWidth: 1,
  borderRadius: 2,
} as const

export function PageViewerHighlightOverlay({
  locators,
  layoutWidth,
  layoutHeight,
  style,
}: {
  locators: Phase1SourceLocator[]
  layoutWidth: number
  layoutHeight: number
  style?: StyleProp<ViewStyle>
}) {
  return (
    <View
      style={[StyleSheet.absoluteFill, { width: layoutWidth, height: layoutHeight }, style]}
      pointerEvents="none"
    >
      {locators.map((loc) => {
        const b = loc.bboxNorm
        if (!b || b.length !== 4) return null
        const [x0, y0, x1, y1] = b
        const w = Math.max(0, (x1 - x0) * layoutWidth)
        const h = Math.max(0, (y1 - y0) * layoutHeight)
        if (w <= 0 || h <= 0) return null
        return (
          <View
            key={loc.id}
            style={[
              styles.highlight,
              {
                left: x0 * layoutWidth,
                top: y0 * layoutHeight,
                width: w,
                height: h,
              },
            ]}
          />
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  highlight: {
    position: 'absolute',
    ...PHASE1_HIGHLIGHT_STYLE,
  },
})
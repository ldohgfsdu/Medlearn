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
      {locators.flatMap((loc) => {
        // Prefer per-visual-line bboxes (multi-line evidence); fall back to
        // the single overall bboxNorm for backward compatibility.
        const lines = loc.bboxNormLines?.filter((b) => b.length === 4)
        const boxes = lines && lines.length > 0
          ? lines
          : loc.bboxNorm?.length === 4
            ? [loc.bboxNorm]
            : []
        return boxes.map((b, i) => {
          const [x0, y0, x1, y1] = b
          const w = Math.max(0, (x1 - x0) * layoutWidth)
          const h = Math.max(0, (y1 - y0) * layoutHeight)
          if (w <= 0 || h <= 0) return null
          return (
            <View
              key={`${loc.id}-${i}`}
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
        })
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
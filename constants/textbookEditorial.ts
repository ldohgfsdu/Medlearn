import { FontFamily, Typography } from '@/constants/theme'

/** Claude-inspired editorial tokens for textbook reading surfaces. */
export const TextbookEditorial = {
  paper: '#FAF8F5',
  surface: '#FFFDF9',
  ink: '#1A1918',
  inkMuted: '#5C5C58',
  inkFaint: '#8A8A84',
  rule: '#E6E4DF',
  accent: '#B45309',
  accentSoft: '#F3EBE3',
  // Highlight overlay for PageViewer source-evidence bounding boxes.
  // Semi-transparent highlighter fill, not outline-only; never bake into webp.
  highlightFill: 'rgba(255, 230, 80, 0.45)',
  highlightBorder: 'rgba(230, 180, 0, 0.35)',
} as const

export const TextbookEditorialFonts = {
  ui: FontFamily.sans,
  reading: FontFamily.serif,
} as const

/** 知识/教材阅读层：显式组合 serif + Typography 尺度 */
export const ReadingTypography = {
  displayLarge: { ...Typography.displayLarge, fontFamily: TextbookEditorialFonts.reading },
  displayMedium: { ...Typography.displayMedium, fontFamily: TextbookEditorialFonts.reading },
  titleLarge: { ...Typography.titleLarge, fontFamily: TextbookEditorialFonts.reading },
  titleMedium: { ...Typography.titleMedium, fontFamily: TextbookEditorialFonts.reading },
  titleSmall: { ...Typography.titleSmall, fontFamily: TextbookEditorialFonts.reading },
  bodyLarge: { ...Typography.bodyLarge, fontFamily: TextbookEditorialFonts.reading },
  bodyMedium: { ...Typography.bodyMedium, fontFamily: TextbookEditorialFonts.reading },
  bodySmall: { ...Typography.bodySmall, fontFamily: TextbookEditorialFonts.reading },
  numberXL: { ...Typography.numberXL, fontFamily: TextbookEditorialFonts.reading },
  numberLarge: { ...Typography.numberLarge, fontFamily: TextbookEditorialFonts.reading },
  numberMedium: { ...Typography.numberMedium, fontFamily: TextbookEditorialFonts.reading },
} as const
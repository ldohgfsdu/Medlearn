/**
 * Medlearn 设计系统
 * 基于 PRD 第 22-28 章规范
 */

// ============================================
// 颜色系统（PRD 23）
// ============================================

export const Colors = {
  // 主色 - clinical green
  primary: {
    50: '#EAF5F1',
    100: '#D4EAE2',
    200: '#AED6C8',
    300: '#7DBBA7',
    400: '#4C9A83',
    500: '#1F7563',
    600: '#175F51',
    700: '#124B40',
    800: '#103C35',
    900: '#0D312B',
  },

  // 语义色
  success: '#2D8A68',
  warning: '#C6832B',
  error: '#C6534A',
  info: '#347C91',
  accent: '#E27A57',
  ink: '#17332C',

  // 中性色
  neutral: {
    50: '#F7F6F2',
    100: '#EFEEE8',
    200: '#E1DFD7',
    300: '#CAC7BD',
    400: '#A09D93',
    500: '#77766F',
    600: '#5C5D57',
    700: '#444943',
    800: '#2D3531',
    900: '#18211E',
  },

  // 掌握度色（PRD 23.4）
  mastery: {
    excellent: '#2D8A68', // 90-100% 精通
    good: '#347C91',      // 70-89% 良好
    fair: '#C6832B',      // 50-69% 一般
    weak: '#D76F43',      // 30-49% 薄弱
    fail: '#C6534A',      // 0-29% 未掌握
  },

  // 语义 token
  background: '#F4F3EE',
  surface: '#FFFDF9',
  surfaceVariant: '#ECEBE5',
  border: '#E0DED5',
  inputBg: '#EEEDE7',
  textPrimary: '#18211E',
  textSecondary: '#5C625D',
  textTertiary: '#8D918B',
  primaryLight: '#EAF5F1',
} as const

// ============================================
// 字体系统（PRD 24）
// ============================================

export const Typography = {
  // 字号体系
  displayLarge: { fontSize: 48, lineHeight: 53, fontWeight: '800' as const },
  displayMedium: { fontSize: 36, lineHeight: 43, fontWeight: '800' as const },
  titleLarge: { fontSize: 20, lineHeight: 26, fontWeight: '700' as const },
  titleMedium: { fontSize: 16, lineHeight: 22, fontWeight: '700' as const },
  titleSmall: { fontSize: 14, lineHeight: 20, fontWeight: '600' as const },
  bodyLarge: { fontSize: 16, lineHeight: 24, fontWeight: '400' as const },
  bodyMedium: { fontSize: 14, lineHeight: 21, fontWeight: '400' as const },
  bodySmall: { fontSize: 12, lineHeight: 18, fontWeight: '400' as const },
  labelLarge: { fontSize: 14, lineHeight: 20, fontWeight: '500' as const },
  labelMedium: { fontSize: 12, lineHeight: 17, fontWeight: '500' as const },
  labelSmall: { fontSize: 10, lineHeight: 14, fontWeight: '500' as const },
} as const

// ============================================
// 间距系统（PRD 25）- 基于 4px 网格
// ============================================

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 20,
  xl: 24,
  '2xl': 32,
  '3xl': 40,
  '4xl': 48,
  '5xl': 64,
} as const

// ============================================
// 圆角（PRD 26.1）
// ============================================

export const BorderRadius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
  '2xl': 24,
  full: 9999,
} as const

// ============================================
// 阴影（PRD 26.2）
// ============================================

export const Shadows = {
  level1: {
    shadowColor: '#17332C',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  level2: {
    shadowColor: '#17332C',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 3,
  },
  level3: {
    shadowColor: '#17332C',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 20,
    elevation: 6,
  },
} as const

// ============================================
// 渐变色对
// ============================================

export const Gradients = {
  primary: [Colors.primary[500], Colors.primary[700]],
  primaryLight: [Colors.primary[400], Colors.primary[600]],
  warm: ['#F59E0B', '#EF4444'],
  ocean: ['#06B6D4', '#3B82F6'],
  forest: ['#10B981', '#059669'],
  sunset: ['#F97316', '#EC4899'],
} as const

// ============================================
// 图标尺寸（PRD 27.2）
// ============================================

export const IconSize = {
  xs: 16,
  sm: 20,
  md: 24,
  lg: 32,
  xl: 48,
  '2xl': 64,
} as const

// ============================================
// 组件尺寸
// ============================================

export const ComponentSize = {
  buttonMinHeight: 48,
  buttonMinWidth: 120,
  inputMinHeight: 48,
  tabBarHeight: 56,
  topBarHeight: 56,
  listItemHeight: 56,
  listItemHeightLarge: 72,
  phaseIndicatorHeight: 64,
} as const

// ============================================
// 动效参数（PRD 31）
// ============================================

export const Animation = {
  durationFast: 150,
  durationNormal: 300,
  durationSlow: 500,
  durationSlower: 1500,
} as const

// ============================================
// 评分等级
// ============================================

export const GradeConfig = {
  excellent: { min: 90, label: '优秀', color: Colors.mastery.excellent },
  good: { min: 70, label: '良好', color: Colors.mastery.good },
  fair: { min: 50, label: '一般', color: Colors.mastery.fair },
  poor: { min: 0, label: '较差', color: Colors.mastery.fail },
} as const

export function getGrade(score: number): { label: string; color: string } {
  if (score >= 90) return GradeConfig.excellent
  if (score >= 70) return GradeConfig.good
  if (score >= 50) return GradeConfig.fair
  return GradeConfig.poor
}

export function getMasteryColor(score: number): string {
  if (score >= 90) return Colors.mastery.excellent
  if (score >= 70) return Colors.mastery.good
  if (score >= 50) return Colors.mastery.fair
  if (score >= 30) return Colors.mastery.weak
  return Colors.mastery.fail
}

/**
 * Medlearn 设计系统
 * 基于 PRD 第 22-28 章规范
 */

import { Platform } from 'react-native'
import { shadowStyle, WEB_SHADOWS } from '@/utils/shadows'

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
  ink: '#17332C', // MedLearn 深墨绿，用于品牌锚点与高强调表面

  // 中性色
  neutral: {
    50: '#FAF9F5',
    100: '#F0EEE6',
    200: '#E8E6DC',
    300: '#D6D3BE',
    400: '#B0AEA5',
    500: '#87867F',
    600: '#6B6A64',
    700: '#4A4945',
    800: '#3D3D3A',
    900: '#141413',
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
  background: '#FAF9F5',
  surface: '#FFFDF9',
  surfaceVariant: '#F0EEE6',
  border: '#E8E6DC',
  inputBg: '#F0EEE6',
  textPrimary: '#141413', // 统一到 neutral.900，告别双色近黑
  textSecondary: '#4A4945',
  textTertiary: '#6B6A64',
  primaryLight: '#EAF5F1',
  // 暖色错误态 — 基于 error 色低透明度，与象牙纸背景协调（替代冷粉红）
  errorBg: 'rgba(198, 83, 74, 0.08)',
  errorBorder: 'rgba(198, 83, 74, 0.24)',
} as const

// ============================================
// 字体系统（PRD 24）— 编辑式排版
// 标题使用紧凑行高（~1.1x），正文使用宽松行高（1.4x）
// ============================================

export const FontFamily = {
  /** 无衬线 — 导航、按钮、标签、表单、仪表盘与功能界面 */
  sans: Platform.select<string>({
    web: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    ios: 'System',
    android: 'sans-serif',
    default: 'sans-serif',
  }) ?? 'sans-serif',
  /** 衬线 — 教材章节、知识内容标题与阅读正文 */
  serif: Platform.select<string>({
    web: 'Georgia, "Noto Serif SC", "Source Han Serif SC", SimSun, serif',
    ios: 'Georgia',
    android: 'serif',
    default: 'serif',
  }) ?? 'serif',
} as const

export const Typography = {
  // 标题层级 — 紧凑行高 (~1.1x)；fontFamily 由调用方按内容层/操作层显式组合
  displayLarge: { fontSize: 48, lineHeight: 53, fontWeight: '600' as const },
  displayMedium: { fontSize: 36, lineHeight: 40, fontWeight: '600' as const },
  titleLarge:  { fontSize: 20, lineHeight: 24, fontWeight: '600' as const },
  titleMedium: { fontSize: 16, lineHeight: 20, fontWeight: '600' as const },
  titleSmall:  { fontSize: 14, lineHeight: 18, fontWeight: '500' as const },
  // 正文层级 — 宽松行高（1.5-1.6x），适合中文医学知识点密度阅读
  bodyLarge:  { fontSize: 16, lineHeight: 24, fontWeight: '400' as const },
  bodyMedium: { fontSize: 15, lineHeight: 24, fontWeight: '400' as const },
  bodySmall:  { fontSize: 13, lineHeight: 18, fontWeight: '400' as const },
  // 标签层级 — 中等行高
  labelLarge:  { fontSize: 14, lineHeight: 20, fontWeight: '400' as const },
  labelMedium: { fontSize: 13, lineHeight: 18, fontWeight: '400' as const },
  labelSmall:  { fontSize: 11, lineHeight: 15, fontWeight: '500' as const },
  // 数字 — 仅字号/行高/字重；医学内容数字用 serif，仪表盘数字用 sans + tabular-nums
  numberXL:     { fontSize: 24, lineHeight: 30, fontWeight: '600' as const },
  numberLarge:  { fontSize: 20, lineHeight: 24, fontWeight: '600' as const },
  numberMedium: { fontSize: 16, lineHeight: 20, fontWeight: '600' as const },
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

const nativeShadows = {
  level1: shadowStyle('level1'),
  level2: shadowStyle('level2'),
  level3: shadowStyle('level3'),
  sheet: shadowStyle('sheet'),
} as const

const webShadows = {
  level1: { boxShadow: WEB_SHADOWS.level1 },
  level2: { boxShadow: WEB_SHADOWS.level2 },
  level3: { boxShadow: WEB_SHADOWS.level3 },
  sheet: { boxShadow: WEB_SHADOWS.sheet },
} as const

export const Shadows = Platform.OS === 'web' ? webShadows : nativeShadows

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

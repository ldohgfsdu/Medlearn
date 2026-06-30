import { Platform, type ViewStyle } from 'react-native'

type ShadowLevel = 'level1' | 'level2' | 'level3' | 'sheet'

export const WEB_SHADOWS: Record<ShadowLevel, string> = {
  level1: '0 1px 2px rgba(23, 51, 44, 0.05)',
  level2: '0 4px 10px rgba(23, 51, 44, 0.08)',
  level3: '0 8px 20px rgba(23, 51, 44, 0.12)',
  sheet: '0 -8px 24px rgba(0, 0, 0, 0.2)',
}

const NATIVE_SHADOWS: Record<ShadowLevel, ViewStyle> = {
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
  sheet: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -8 },
    shadowOpacity: 0.2,
    shadowRadius: 24,
    elevation: 8,
  },
}

export function shadowStyle(level: ShadowLevel): ViewStyle {
  if (Platform.OS === 'web') {
    return { boxShadow: WEB_SHADOWS[level] } as ViewStyle
  }
  return NATIVE_SHADOWS[level]
}
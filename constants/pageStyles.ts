import { StyleSheet } from 'react-native'
import { BorderRadius, Colors, Typography, Spacing } from '@/constants/theme'
import { Layout } from '@/constants/layout'

/** 跨页面复用的紧凑移动端样式 */
export const pageStyles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Layout.screenPaddingBottom,
  },
  pageIntro: {
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.md,
  },
  pageIntroTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  pageIntroText: {
    fontSize: 15,
    lineHeight: 24,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  sectionMeta: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textTertiary,
  },
  listCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    paddingHorizontal: Layout.cardPadding,
  },
  listRow: {
    minHeight: Layout.listRowHeight,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  rowDivider: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  surfaceCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Layout.cardRadius,
    padding: Layout.cardPadding,
  },
  primaryBtn: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.primary[700],
    borderRadius: BorderRadius.full,
  },
  primaryBtnText: {
    ...Typography.labelLarge,
    color: Colors.surface,
    fontWeight: '700',
  },
  secondaryBtn: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.full,
  },
  inputArea: {
    backgroundColor: Colors.surface,
    borderRadius: Layout.cardRadius,
    padding: Layout.cardPadding,
    minHeight: 160,
    borderWidth: 1,
    borderColor: Colors.border,
  },
})
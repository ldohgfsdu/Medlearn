import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert } from 'react-native'
import { useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import Constants from 'expo-constants'
import { useAuth } from '@/hooks/useAuth'
import { useProfileStats } from '@/hooks/useProfileStats'
import { Colors, Typography, Spacing, BorderRadius } from '@/constants/theme'
import { Layout } from '@/constants/layout'

const MENU_ITEMS: {
  icon: keyof typeof Ionicons.glyphMap
  label: string
  note: string
  route?: '/(tabs)/analytics' | '/settings/ai'
  action?: 'about' | 'feedback'
}[] = [
  { icon: 'analytics-outline', label: '学习报告', note: '查看能力维度与进步趋势', route: '/(tabs)/analytics' },
  { icon: 'ribbon-outline', label: '学习成就', note: '里程碑与真实学习记录', route: '/(tabs)/analytics' },
  { icon: 'sparkles-outline', label: 'AI 设置', note: '配置对话模型、API Key 与 Embedding', route: '/settings/ai' },
  { icon: 'chatbox-outline', label: '反馈建议', note: '描述 App 问题、页面与操作步骤', action: 'feedback' },
  { icon: 'information-circle-outline', label: '关于 Medlearn', note: '版本、隐私与使用说明', action: 'about' },
]

export default function ProfileScreen() {
  const router = useRouter()
  const { user, signOut } = useAuth()
  const nickname = user?.user_metadata?.nickname || '同学'
  const email = user?.email || ''
  const appVersion = Constants.expoConfig?.version ?? '2.0.0'
  const { data: stats } = useProfileStats(user?.id)
  const { xp = 0, cases = 0, learningDays = 0 } = stats ?? {}

  const handleMenuPress = (item: (typeof MENU_ITEMS)[number]) => {
    if (item.route) {
      router.push(item.route)
      return
    }

    if (item.action === 'feedback') {
      Alert.alert(
        '反馈建议',
        '请描述你遇到的问题、所在页面和操作步骤，便于我们复现。\n\n本入口仅用于产品反馈，不提供医学问答或诊疗咨询。',
      )
      return
    }

    Alert.alert(
      '关于 Medlearn',
      `Medlearn ${appVersion}\n医学教育训练工具，不提供医疗建议。AI 生成内容可能不准确，不能用于真实患者诊断或治疗。`,
    )
  }

  const handleSignOut = async () => {
    Alert.alert('退出登录', '确定要退出吗？', [
      { text: '取消', style: 'cancel' },
      {
        text: '退出',
        style: 'destructive',
        onPress: async () => {
          await signOut()
          router.replace('/(auth)/login')
        },
      },
    ])
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      <View style={styles.profileCard}>
        <View style={styles.profileTop}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{nickname.slice(0, 1)}</Text>
          </View>
          <View style={styles.profileCopy}>
            <Text style={styles.nickname}>{nickname}</Text>
            <Text style={styles.email}>{email}</Text>
            <Text style={styles.profileMeta}>
              累计学习 {learningDays} 天 · 完成 {cases} 个病例
            </Text>
          </View>
        </View>

        <View style={styles.statsRow}>
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{xp}</Text>
            <Text style={styles.statLabel}>学习 XP</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{cases}</Text>
            <Text style={styles.statLabel}>完成病例</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{learningDays}</Text>
            <Text style={styles.statLabel}>学习日</Text>
          </View>
        </View>
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>我的学习</Text>
        <Text style={styles.sectionCount}>{String(MENU_ITEMS.length).padStart(2, '0')}</Text>
      </View>

      <View style={styles.menuGroup}>
        {MENU_ITEMS.map((item, index) => (
          <TouchableOpacity
            key={item.label}
            style={[styles.menuItem, index < MENU_ITEMS.length - 1 && styles.menuItemBorder]}
            onPress={() => handleMenuPress(item)}
            activeOpacity={0.65}
          >
            <View style={styles.menuIcon}>
              <Ionicons name={item.icon} size={20} color={Colors.primary[700]} />
            </View>
            <View style={styles.menuCopy}>
              <Text style={styles.menuLabel}>{item.label}</Text>
              <Text style={styles.menuNote}>{item.note}</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={Colors.neutral[400]} />
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={styles.signOutButton} onPress={handleSignOut} activeOpacity={0.7}>
        <Ionicons name="log-out-outline" size={18} color={Colors.error} />
        <Text style={styles.signOutText}>退出登录</Text>
      </TouchableOpacity>

      <Text style={styles.version}>MEDLEARN / VERSION {appVersion}</Text>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Layout.screenPaddingBottom,
  },
  profileCard: {
    backgroundColor: Colors.surface,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Layout.cardPadding,
    marginBottom: Layout.sectionGap,
  },
  profileTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Colors.primary[50],
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 20,
    fontWeight: '800',
    color: Colors.primary[700],
  },
  profileCopy: {
    flex: 1,
  },
  nickname: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
  },
  email: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textTertiary,
    marginTop: 2,
  },
  profileMeta: {
    fontSize: 13,
    lineHeight: 18,
    color: Colors.textSecondary,
    marginTop: Spacing.xs,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 18,
    lineHeight: 22,
    fontWeight: '800',
    color: Colors.textPrimary,
  },
  statLabel: {
    fontSize: 12,
    lineHeight: 16,
    color: Colors.textTertiary,
    marginTop: 3,
  },
  statDivider: {
    width: StyleSheet.hairlineWidth,
    height: 32,
    backgroundColor: Colors.border,
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
  sectionCount: {
    fontSize: 13,
    color: Colors.textTertiary,
  },
  menuGroup: {
    backgroundColor: Colors.surface,
    borderRadius: Layout.cardRadius,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Layout.cardPadding,
    marginBottom: Spacing.md,
  },
  menuItem: {
    minHeight: Layout.listRowHeight,
    flexDirection: 'row',
    alignItems: 'center',
  },
  menuItemBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  menuIcon: {
    width: Layout.iconWrap,
    height: Layout.iconWrap,
    borderRadius: Layout.iconWrap / 2,
    backgroundColor: Colors.primary[50],
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.md,
  },
  menuCopy: {
    flex: 1,
  },
  menuLabel: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  menuNote: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    marginTop: 3,
  },
  signOutButton: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: '#E5C7C2',
    backgroundColor: '#FAF0ED',
  },
  signOutText: {
    ...Typography.labelLarge,
    color: Colors.error,
    fontWeight: '700',
  },
  version: {
    fontSize: 9,
    lineHeight: 13,
    fontWeight: '700',
    letterSpacing: 1.2,
    color: Colors.textTertiary,
    textAlign: 'center',
    marginTop: Spacing.lg,
  },
})

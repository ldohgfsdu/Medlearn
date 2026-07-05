import { Tabs, router } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Colors, FontFamily, Spacing } from '@/constants/theme'

// 浮动 Pill Tab Bar 基础高度（pill 62 + 顶部 12 呼吸），不含 safe area bottom inset。
// 页面 paddingBottom 应叠加此值 + insets.bottom，避免内容被浮动栏遮挡。
export const FLOATING_TAB_BAR_BASE_HEIGHT = 74

const PILL_HEIGHT = 62
const PILL_RADIUS = 36
const TAB_ITEM_RADIUS = 26
const TAB_ICON_SIZE = 20
const TAB_LABEL_SIZE = 11
const TAB_BAR_HORIZONTAL_PADDING = 21

type TabIconName = keyof typeof Ionicons.glyphMap

interface TabConfig {
  name: string
  title: string
  icon: TabIconName
  activeIcon: TabIconName
}

// 仅列出可见 tab；href: null 的 ask / analytics 不会渲染 tab item。
const VISIBLE_TABS: TabConfig[] = [
  { name: 'index', title: '首页', icon: 'home-outline', activeIcon: 'home' },
  { name: 'learn', title: '知识', icon: 'book-outline', activeIcon: 'book' },
  { name: 'cases', title: '病例', icon: 'pulse-outline', activeIcon: 'pulse' },
  { name: 'profile', title: '我的', icon: 'person-outline', activeIcon: 'person' },
]

// expo-router v56 未公开导出 BottomTabBarProps，且其 navigation.emit 重载返回类型
// 与 react-navigation 标准不一致（EventArg 不含 defaultPrevented 字段），
// 这里对 navigation 用宽松类型，保留 state / descriptors 的结构类型安全。
type FloatingTabBarProps = {
  state: { index: number; routes: { key: string; name: string }[] }
  descriptors: Record<string, { options: Record<string, unknown> }>
  navigation: any
}

function FloatingTabBar({ state, descriptors, navigation }: FloatingTabBarProps) {
  const insets = useSafeAreaInsets()
  return (
    <View
      style={[
        styles.tabBarWrap,
        { paddingBottom: insets.bottom > 0 ? insets.bottom : Spacing.sm },
      ]}
    >
      <View style={styles.pill}>
        {state.routes.map((route, index) => {
          const config = VISIBLE_TABS.find((c) => c.name === route.name)
          // 跳过 href:null 的隐藏路由（ask / analytics）
          if (!config) return null
          const focused = index === state.index
          const { options } = descriptors[route.key]
          const onPress = () => {
            const event = navigation.emit({
              type: 'tabPress',
              target: route.key,
              canPreventDefault: true,
            })
            if (!event.defaultPrevented) {
              navigation.navigate(route.name)
            }
          }
          const onLongPress = () => {
            navigation.emit({ type: 'tabLongPress', target: route.key })
          }
          const accessibilityLabel =
            (typeof options.tabBarAccessibilityLabel === 'string'
              ? options.tabBarAccessibilityLabel
              : undefined) ?? config.title
          return (
            <Pressable
              key={route.key}
              style={[styles.tabItem, focused && styles.tabItemActive]}
              onPress={onPress}
              onLongPress={onLongPress}
              accessibilityRole="button"
              accessibilityState={focused ? { selected: true } : {}}
              accessibilityLabel={accessibilityLabel}
            >
              <Ionicons
                name={focused ? config.activeIcon : config.icon}
                size={TAB_ICON_SIZE}
                color={focused ? Colors.surface : Colors.neutral[400]}
              />
              <Text
                style={[
                  styles.tabLabel,
                  focused ? styles.tabLabelActive : styles.tabLabelInactive,
                ]}
              >
                {config.title}
              </Text>
            </Pressable>
          )
        })}
      </View>
    </View>
  )
}

export default function TabsLayout() {
  return (
    <Tabs
      tabBar={(props) => <FloatingTabBar {...props} />}
      screenOptions={{
        headerStyle: {
          backgroundColor: Colors.background,
        },
        headerTintColor: Colors.textPrimary,
        headerTitleStyle: { fontWeight: '600', fontSize: 17, fontFamily: FontFamily.sans },
        headerShadowVisible: false,
        headerTitleAlign: 'left',
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '首页',
          headerTitle: 'MedLearn',
          headerShown: false,
        }}
      />
      <Tabs.Screen
        name="learn"
        options={{
          title: '知识',
          headerTitle: '知识地图',
          headerRight: () => (
            <Pressable
              onPress={() => router.push('/search')}
              style={styles.headerAction}
              accessibilityLabel="搜索知识点"
              accessibilityRole="button"
            >
              <Ionicons name="search-outline" size={22} color={Colors.primary[700]} />
            </Pressable>
          ),
        }}
      />
      <Tabs.Screen
        name="cases"
        options={{
          title: '病例',
          headerTitle: '病例中心',
        }}
      />
      <Tabs.Screen
        name="ask"
        options={{
          href: null,
          title: '智能问答',
          headerTitle: '智能问答',
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: '我的',
          headerTitle: '个人中心',
        }}
      />
      {/* 隐藏的页面 */}
      <Tabs.Screen
        name="analytics"
        options={{
          href: null,
          headerTitle: '学习报告',
        }}
      />
    </Tabs>
  )
}

const styles = StyleSheet.create({
  tabBarWrap: {
    // 占位（非 absolute）：内容自动停在 tab bar 上方，无需每个页面单独留 padding。
    paddingTop: Spacing.md,
    paddingHorizontal: TAB_BAR_HORIZONTAL_PADDING,
    // 与页面同色，pill 浮在同色背景上，符合设计稿"纯背景过渡"。
    backgroundColor: Colors.background,
  },
  pill: {
    height: PILL_HEIGHT,
    borderRadius: PILL_RADIUS,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    padding: Spacing.xs,
    backgroundColor: Colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: Colors.border,
  },
  tabItem: {
    flex: 1,
    height: PILL_HEIGHT - Spacing.xs * 2,
    borderRadius: TAB_ITEM_RADIUS,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 3,
  },
  tabItemActive: {
    // active 用 ink 实色填充，不加阴影；陶土 accent 仅用于学习行动，不用于导航。
    backgroundColor: Colors.ink,
  },
  tabLabel: {
    fontSize: TAB_LABEL_SIZE,
    lineHeight: 14,
    fontFamily: FontFamily.sans,
  },
  tabLabelActive: {
    fontWeight: '600',
    color: Colors.surface,
  },
  tabLabelInactive: {
    fontWeight: '500',
    color: Colors.neutral[400],
  },
  headerAction: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.sm,
  },
})

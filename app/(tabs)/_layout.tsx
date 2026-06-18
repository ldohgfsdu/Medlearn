import { Tabs, router } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { Platform, Pressable, StyleSheet, View, type ColorValue } from 'react-native'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { Colors, Shadows, Spacing } from '@/constants/theme'

export default function TabsLayout() {
  const insets = useSafeAreaInsets()
  const tabBarHeight = Platform.OS === 'ios' ? 78 + insets.bottom : 72

  const renderTabIcon = (
    name: keyof typeof Ionicons.glyphMap,
    activeName: keyof typeof Ionicons.glyphMap,
    color: ColorValue,
    size: number,
    focused: boolean,
  ) => (
    <View style={[styles.iconWrap, focused && styles.iconWrapActive]}>
      <Ionicons name={focused ? activeName : name} size={focused ? size - 1 : size} color={color} />
    </View>
  )

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: Colors.primary[700],
        tabBarInactiveTintColor: Colors.neutral[400],
        tabBarStyle: {
          backgroundColor: Colors.surface,
          borderTopColor: Colors.border,
          borderTopWidth: StyleSheet.hairlineWidth,
          height: tabBarHeight,
          paddingBottom: insets.bottom > 0 ? insets.bottom : 8,
          paddingTop: 6,
          ...Shadows.level1,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '700',
          letterSpacing: 0.2,
          marginTop: 1,
        },
        tabBarShowLabel: true,
        headerStyle: {
          backgroundColor: Colors.background,
        },
        headerTintColor: Colors.textPrimary,
        headerTitleStyle: { fontWeight: '700', fontSize: 17 },
        headerShadowVisible: false,
        headerTitleAlign: 'left',
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '首页',
          headerTitle: 'Medlearn',
          headerShown: false,
          tabBarIcon: ({ color, size, focused }) =>
            renderTabIcon('home-outline', 'home', color, size, focused),
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
          tabBarIcon: ({ color, size, focused }) =>
            renderTabIcon('book-outline', 'book', color, size, focused),
        }}
      />
      <Tabs.Screen
        name="cases"
        options={{
          title: '病例',
          headerTitle: '病例中心',
          tabBarIcon: ({ color, size, focused }) =>
            renderTabIcon('pulse-outline', 'pulse', color, size, focused),
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
          tabBarIcon: ({ color, size, focused }) =>
            renderTabIcon('person-outline', 'person', color, size, focused),
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
  iconWrap: {
    width: 44,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconWrapActive: {
    backgroundColor: Colors.primary[50],
  },
  headerAction: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.sm,
  },
})

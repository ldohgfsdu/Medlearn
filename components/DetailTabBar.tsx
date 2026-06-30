import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Colors, Typography, Spacing } from '@/constants/theme'

export interface DetailTabItem<T extends string> {
  key: T
  label: string
  icon: React.ComponentProps<typeof Ionicons>['name']
}

interface DetailTabBarProps<T extends string> {
  tabs: DetailTabItem<T>[]
  activeKey: T
  onChange: (key: T) => void
}

export function DetailTabBar<T extends string>({
  tabs,
  activeKey,
  onChange,
}: DetailTabBarProps<T>) {
  return (
    <View style={styles.tabBar}>
      {tabs.map((tab) => {
        const active = activeKey === tab.key
        return (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, active && styles.tabActive]}
            onPress={() => onChange(tab.key)}
            activeOpacity={0.7}
          >
            <Ionicons
              name={tab.icon}
              size={17}
              color={active ? Colors.primary[700] : Colors.textTertiary}
            />
            <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
    backgroundColor: Colors.background,
  },
  tab: {
    flex: 1,
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: Colors.primary[700],
  },
  tabLabel: {
    ...Typography.labelMedium,
    color: Colors.textTertiary,
  },
  tabLabelActive: {
    color: Colors.primary[700],
    fontWeight: '700',
  },
})
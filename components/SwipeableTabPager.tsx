import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  NativeScrollEvent,
  NativeSyntheticEvent,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  useWindowDimensions,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { Colors, Typography, Spacing } from '@/constants/theme'

export interface SwipeableTab {
  key: string
  label: string
  icon: React.ComponentProps<typeof Ionicons>['name']
}

interface SwipeableTabPagerProps {
  tabs: SwipeableTab[]
  pages: React.ReactNode[]
  initialIndex?: number
}

export function SwipeableTabPager({ tabs, pages, initialIndex = 0 }: SwipeableTabPagerProps) {
  const { width } = useWindowDimensions()
  const pagerRef = useRef<ScrollView>(null)
  const clampedIndex = Math.max(0, Math.min(initialIndex, tabs.length - 1))
  const [activeIndex, setActiveIndex] = useState(clampedIndex)
  const [prevClampedIndex, setPrevClampedIndex] = useState(clampedIndex)

  if (clampedIndex !== prevClampedIndex) {
    setPrevClampedIndex(clampedIndex)
    setActiveIndex(clampedIndex)
  }

  useEffect(() => {
    pagerRef.current?.scrollTo({ x: clampedIndex * width, animated: false })
  }, [clampedIndex, width])

  const scrollToIndex = useCallback((index: number) => {
    const next = Math.max(0, Math.min(index, tabs.length - 1))
    setActiveIndex(next)
    pagerRef.current?.scrollTo({ x: next * width, animated: true })
  }, [tabs.length, width])

  const handleMomentumEnd = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const index = Math.round(event.nativeEvent.contentOffset.x / width)
    if (index !== activeIndex) {
      setActiveIndex(index)
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.tabBar}>
        {tabs.map((tab, index) => {
          const active = index === activeIndex
          return (
            <TouchableOpacity
              key={tab.key}
              style={[styles.tab, active && styles.tabActive]}
              onPress={() => scrollToIndex(index)}
              activeOpacity={0.7}
            >
              <Ionicons
                name={tab.icon}
                size={17}
                color={active ? Colors.primary[700] : Colors.textTertiary}
              />
              <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>{tab.label}</Text>
            </TouchableOpacity>
          )
        })}
      </View>

      <ScrollView
        ref={pagerRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={handleMomentumEnd}
        scrollEventThrottle={16}
        decelerationRate="fast"
        contentOffset={{ x: initialIndex * width, y: 0 }}
        style={styles.pager}
      >
        {pages.map((page, index) => (
          <View key={tabs[index]?.key ?? `page-${index}`} style={{ width }}>
            {page}
          </View>
        ))}
      </ScrollView>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
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
  pager: {
    flex: 1,
  },
})

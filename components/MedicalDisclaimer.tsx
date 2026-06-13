import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Typography, Spacing, BorderRadius } from '@/constants/theme';

/**
 * 医学合规免责声明组件
 * 根据 agent.md 规范要求强制显示
 */
export const MedicalDisclaimer = () => (
  <View style={styles.container}>
    <Ionicons name="shield-checkmark-outline" size={14} color={Colors.textTertiary} />
    <Text style={styles.text}>⚠️ AI 生成内容，仅用于学习，不构成医学建议</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    padding: Spacing.xs,
    backgroundColor: Colors.neutral[100],
    borderRadius: BorderRadius.sm,
    flexDirection: 'row',
    gap: Spacing.xs,
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: Spacing.xs,
    opacity: 0.8,
  },
  text: {
    ...Typography.labelSmall,
    color: Colors.textTertiary,
    fontSize: 10,
  },
});

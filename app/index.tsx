import { View, Text, StyleSheet, TouchableOpacity } from 'react-native'
import { useRouter } from 'expo-router'

export default function HomeScreen() {
  const router = useRouter()

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.greeting}>你好, 同学</Text>
        <View style={styles.streakRow}>
          <Text style={styles.streakIcon}>🔥</Text>
          <Text style={styles.streakText}>已连续学习 3 天</Text>
        </View>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statCardPrimary}>
          <Text style={styles.statLabel}>今日待复习</Text>
          <Text style={styles.statValueWhite}>12</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={styles.statLabel}>本周费曼数</Text>
          <Text style={styles.statValue}>5</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>思维训练</Text>
      <TouchableOpacity
        style={styles.ctaCard}
        onPress={() => router.push('/map')}
      >
        <View>
          <Text style={styles.ctaTitle}>📚 进入知识地图</Text>
          <Text style={styles.ctaSubtitle}>内科学 192 个知识点待掌握</Text>
        </View>
        <View style={styles.ctaButton}>
          <Text style={styles.ctaButtonText}>去学习</Text>
        </View>
      </TouchableOpacity>

      <Text style={styles.sectionTitle}>最近复述</Text>
      {['心力衰竭', '肺炎', '高血压'].map((item, i) => (
        <View key={i} style={styles.reviewItem}>
          <Text style={styles.reviewText}>✅ {item}</Text>
          <Text style={styles.reviewTime}>2小时前</Text>
        </View>
      ))}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f7f8fa',
  },
  header: {
    marginBottom: 24,
  },
  greeting: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1a1a1a',
  },
  streakRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  streakIcon: {
    fontSize: 14,
  },
  streakText: {
    fontSize: 14,
    color: '#666',
    marginLeft: 4,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 24,
  },
  statCardPrimary: {
    flex: 1,
    backgroundColor: '#007aff',
    padding: 16,
    borderRadius: 12,
  },
  statCard: {
    flex: 1,
    backgroundColor: '#fff',
    padding: 16,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  statLabel: {
    fontSize: 13,
    color: 'rgba(255,255,255,0.8)',
  },
  statValueWhite: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#fff',
    marginTop: 4,
  },
  statValue: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#007aff',
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 12,
    color: '#1a1a1a',
  },
  ctaCard: {
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 12,
    marginBottom: 24,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    shadowColor: '#007aff',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 3,
  },
  ctaTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
  },
  ctaSubtitle: {
    fontSize: 13,
    color: '#888',
    marginTop: 2,
  },
  ctaButton: {
    backgroundColor: '#007aff',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 16,
  },
  ctaButtonText: {
    color: '#fff',
    fontSize: 14,
  },
  reviewItem: {
    backgroundColor: '#fff',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  reviewText: {
    fontSize: 15,
    color: '#333',
  },
  reviewTime: {
    fontSize: 13,
    color: '#ccc',
  },
})

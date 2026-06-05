import React, { useState } from 'react'
import { View, Text, StyleSheet, TextInput, TouchableOpacity, Alert, ActivityIndicator } from 'react-native'
import { useLocalSearchParams, useRouter } from 'expo-router'
import { evaluateWithRAG } from '@/services/ai'

export default function FeynmanScreen() {
  const router = useRouter()
  const params = useLocalSearchParams<{ id: string; title: string }>()
  const nodeTitle = params.title || '未知知识点'

  const [transcript, setTranscript] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const handleEvaluate = async () => {
    if (!transcript.trim()) return
    setLoading(true)
    try {
      const res = await evaluateWithRAG(nodeTitle, transcript)
      setResult(res)
    } catch (e) {
      Alert.alert('评估失败', '请检查网络连接后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View style={styles.container}>
      <TouchableOpacity onPress={() => router.back()}>
        <Text style={styles.backLink}>← 返回知识地图</Text>
      </TouchableOpacity>

      <Text style={styles.title}>费曼复述：{nodeTitle}</Text>

      <TextInput
        style={styles.textInput}
        placeholder="请试着向别人解释一下这个知识点的机制..."
        placeholderTextColor="#999"
        multiline
        numberOfLines={6}
        textAlignVertical="top"
        value={transcript}
        onChangeText={setTranscript}
      />

      <TouchableOpacity
        style={[styles.submitBtn, loading && styles.submitBtnDisabled]}
        onPress={handleEvaluate}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.submitBtnText}>提交评估</Text>
        )}
      </TouchableOpacity>

      {result && (
        <View style={styles.resultCard}>
          <View style={styles.scoreRow}>
            <Text style={styles.scoreValue}>{result.score}</Text>
            <Text style={styles.scoreUnit}>分</Text>
          </View>
          <Text style={styles.feedback}>{result.feedback}</Text>

          <Text style={styles.missingTitle}>漏掉的关键点：</Text>
          {result.missingPoints?.map((p: string, i: number) => (
            <Text key={i} style={styles.missingItem}>• {p}</Text>
          ))}

          <View style={styles.referenceRow}>
            <Text style={styles.referenceText}>
              📚 评估依据：{result.reference}
            </Text>
          </View>
        </View>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f7f8fa',
  },
  backLink: {
    color: '#007aff',
    fontSize: 14,
    marginBottom: 12,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 16,
    color: '#1a1a1a',
  },
  textInput: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 14,
    fontSize: 15,
    color: '#333',
    minHeight: 150,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  submitBtn: {
    backgroundColor: '#007aff',
    paddingVertical: 14,
    borderRadius: 22,
    alignItems: 'center',
  },
  submitBtnDisabled: {
    opacity: 0.6,
  },
  submitBtnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  resultCard: {
    marginTop: 24,
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 4,
  },
  scoreRow: {
    alignItems: 'center',
    marginBottom: 16,
  },
  scoreValue: {
    fontSize: 48,
    fontWeight: 'bold',
    color: '#007aff',
  },
  scoreUnit: {
    fontSize: 14,
    color: '#888',
    marginLeft: 4,
  },
  feedback: {
    fontSize: 15,
    color: '#333',
    lineHeight: 24,
    marginBottom: 16,
  },
  missingTitle: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#ff3b30',
  },
  missingItem: {
    fontSize: 13,
    color: '#666',
    marginTop: 2,
  },
  referenceRow: {
    marginTop: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#eee',
    paddingTop: 12,
  },
  referenceText: {
    fontSize: 11,
    color: '#999',
  },
})

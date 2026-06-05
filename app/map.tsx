import React, { useState } from 'react'
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native'
import { useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useSubjects, useTreeBySubject } from '@/hooks/useKnowledge'

export default function KnowledgeMapScreen() {
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null)
  const router = useRouter()

  const { data: subjects, isLoading: loadingSubjects } = useSubjects()
  const { data: tree, isLoading: loadingTree } = useTreeBySubject(selectedSubject || '')

  const handleNodeClick = (node: any) => {
    router.push({
      pathname: '/feynman',
      params: { id: node.id, title: node.title },
    })
  }

  if (loadingSubjects) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007aff" />
        <Text style={styles.loadingText}>正在加载内科学结构...</Text>
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <Text style={styles.headerTitle}>
        {selectedSubject ? `内科学 > ${selectedSubject}` : '内科学（第10版）知识地图'}
      </Text>

      {!selectedSubject ? (
        <View style={styles.grid}>
          {subjects?.map((subject) => (
            <TouchableOpacity
              key={subject}
              style={styles.systemCard}
              onPress={() => setSelectedSubject(subject)}
            >
              <Ionicons name="fitness" size={28} color="#007aff" />
              <Text style={styles.systemName}>{subject}</Text>
            </TouchableOpacity>
          ))}
        </View>
      ) : (
        <ScrollView style={{ flex: 1 }}>
          <TouchableOpacity onPress={() => setSelectedSubject(null)}>
            <Text style={styles.backLink}>← 返回系统列表</Text>
          </TouchableOpacity>

          {loadingTree ? (
            <ActivityIndicator size="small" color="#007aff" style={{ marginTop: 20 }} />
          ) : (
            Object.entries(tree || {}).map(([chapter, nodes]) => (
              <View key={chapter} style={styles.chapterCard}>
                <View style={styles.chapterHeader}>
                  <Ionicons name="book" size={16} color="#0056b3" />
                  <Text style={styles.chapterTitle}>{chapter}</Text>
                </View>
                {nodes.map((node: any) => (
                  <TouchableOpacity
                    key={node.id}
                    style={styles.nodeItem}
                    onPress={() => handleNodeClick(node)}
                  >
                    <Text style={styles.nodeTitle}>{node.title}</Text>
                    <Ionicons name="chevron-forward" size={16} color="#ccc" />
                  </TouchableOpacity>
                ))}
              </View>
            ))
          )}
        </ScrollView>
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
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 15,
    color: '#666',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 16,
    color: '#1a1a1a',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  systemCard: {
    width: '48%',
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 12,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  systemName: {
    marginTop: 10,
    fontSize: 15,
    fontWeight: 'bold',
    textAlign: 'center',
    color: '#333',
  },
  backLink: {
    color: '#007aff',
    fontSize: 14,
    marginBottom: 12,
  },
  chapterCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    marginBottom: 10,
    overflow: 'hidden',
  },
  chapterHeader: {
    backgroundColor: '#f0f7ff',
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
  },
  chapterTitle: {
    marginLeft: 8,
    fontSize: 15,
    fontWeight: 'bold',
    color: '#0056b3',
  },
  nodeItem: {
    padding: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#f0f0f0',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  nodeTitle: {
    fontSize: 15,
    color: '#444',
  },
})

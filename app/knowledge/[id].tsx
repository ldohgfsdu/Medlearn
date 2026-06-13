import { useLocalSearchParams, useRouter } from 'expo-router';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { getKnowledgePoint } from '../lib/knowledge';
// Demo recovery: lucide-react-native disabled for web export
// import { ChevronLeft, BookOpen } from 'lucide-react-native';

export default function KnowledgeDetailPage() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  const { data: point, isLoading, error } = useQuery({
    queryKey: ['knowledge', id],
    queryFn: () => getKnowledgePoint(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <View className="flex-1 bg-zinc-950 items-center justify-center">
        <ActivityIndicator size="large" color="#22c55e" />
        <Text className="text-zinc-400 mt-4">加载知识点...</Text>
      </View>
    );
  }

  if (error || !point) {
    return (
      <View className="flex-1 bg-zinc-950 p-6 items-center justify-center">
        <Text className="text-red-400 text-xl mb-2">知识点不存在</Text>
        <Text className="text-zinc-500 text-center">ID: {id}</Text>
        <TouchableOpacity 
          onPress={() => router.back()}
          className="mt-8 bg-zinc-800 px-6 py-3 rounded-xl"
        >
          <Text className="text-white">返回</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View className="flex-1 bg-zinc-950">
      {/* Breadcrumb */}
      <View className="px-6 pt-12 pb-4 border-b border-zinc-800 bg-zinc-900">
        <TouchableOpacity 
          onPress={() => router.back()}
          className="flex-row items-center gap-1 mb-3"
        >
          {/* <ChevronLeft size={20} color="#a1a1aa" /> */}
          <Text className="text-zinc-400 text-sm">← 返回</Text>
        </TouchableOpacity>
        <Text className="text-sm text-emerald-400">知识库</Text>
      </View>

      <ScrollView className="flex-1 px-6 pt-6">
        <View className="flex-row items-center gap-3 mb-4">
          {/* <BookOpen size={28} color="#22c55e" /> */}
          <Text className="text-2xl">📘</Text>
          <Text className="text-3xl font-bold text-white flex-1">{point.title}</Text>
        </View>

        {point.aliases && point.aliases.length > 0 && (
          <View className="flex-row flex-wrap gap-2 mb-6">
            {point.aliases.map((alias: string) => (
              <View key={alias} className="bg-zinc-800 px-3 py-1 rounded-full">
                <Text className="text-emerald-400 text-sm">{alias}</Text>
              </View>
            ))}
          </View>
        )}

        {point.definition && (
          <View className="mb-8">
            <Text className="text-lg font-semibold text-white mb-3">定义</Text>
            <Text className="text-zinc-300 leading-6 text-base">
              {typeof point.definition === 'string' ? point.definition : point.definition.content}
            </Text>
          </View>
        )}

        {point.mechanism && (
          <View className="mb-8">
            <Text className="text-lg font-semibold text-white mb-3">机制</Text>
            <Text className="text-zinc-300 leading-6 text-base">
              {point.mechanism}
            </Text>
          </View>
        )}

        {point.clinical_relevance && (
          <View className="mb-8">
            <Text className="text-lg font-semibold text-white mb-3">临床意义</Text>
            <Text className="text-zinc-300 leading-6 text-base">
              {point.clinical_relevance}
            </Text>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

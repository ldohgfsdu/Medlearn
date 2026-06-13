import { useState } from 'react';
import { View, Text, TextInput, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { searchKnowledge } from '@/app/lib/knowledge';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const router = useRouter();

  const { data: results, isLoading } = useQuery({
    queryKey: ['search', query],
    queryFn: () => searchKnowledge(query),
    enabled: query.length > 1,
  });

  return (
    <View className="flex-1 bg-zinc-950 p-4">
      <Text className="text-2xl font-bold text-white mb-6">知识搜索</Text>
      
      <TextInput
        className="bg-zinc-900 text-white p-4 rounded-xl mb-6 text-base"
        placeholder="搜索疾病、症状、检查、药物..."
        placeholderTextColor="#666"
        value={query}
        onChangeText={setQuery}
        autoCapitalize="none"
      />

      {isLoading && (
        <ActivityIndicator size="large" color="#22c55e" />
      )}

      <ScrollView>
        {results?.map((item: any) => (
          <TouchableOpacity
            key={item.id}
            onPress={() => router.push(`/knowledge/${item.id}`)}
            className="bg-zinc-900 p-5 rounded-2xl mb-4 active:opacity-70"
          >
            <View className="flex-row justify-between items-start mb-2">
              <Text className="text-lg font-semibold text-white flex-1">
                {item.title}
              </Text>
              <Text className="text-xs text-emerald-400 bg-emerald-950 px-2 py-1 rounded-full">
                {item.type}
              </Text>
            </View>
            
            <Text className="text-zinc-400 text-sm line-clamp-2 mb-3">
              {item.summary || item.definition?.content?.slice(0, 120)}...
            </Text>
            
            <View className="flex-row gap-2">
              {item.aliases?.slice(0, 2).map((alias: string) => (
                <Text key={alias} className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded">
                  {alias}
                </Text>
              ))}
            </View>
          </TouchableOpacity>
        ))}

        {query.length > 1 && results?.length === 0 && (
          <Text className="text-zinc-500 text-center py-12">
            没有找到匹配的结果
          </Text>
        )}
      </ScrollView>
    </View>
  );
}

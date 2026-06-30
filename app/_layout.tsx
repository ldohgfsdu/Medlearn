import { useEffect } from 'react'
import { Stack, useRouter, useSegments } from 'expo-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/hooks/useAuth'
import { Colors } from '@/constants/theme'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import '../global.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const segments = useSegments()
  const router = useRouter()

  useEffect(() => {
    if (loading) return

    const inAuthGroup = segments[0] === '(auth)'
    const isPublicRoute = segments[0] === 'map' || segments[0] === 'textbook'

    if (!user && !inAuthGroup && !isPublicRoute) {
      // 未登录，跳转登录页
      router.replace('/(auth)/login')
    } else if (user && inAuthGroup) {
      // 已登录，跳转首页
      router.replace('/(tabs)')
    }
  }, [user, loading, segments, router])

  return <>{children}</>
}

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthGuard>
          <ErrorBoundary>
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: Colors.background },
              headerTintColor: Colors.ink,
              headerTitleStyle: { fontWeight: '800', fontSize: 17 },
              headerShadowVisible: false,
              headerBackButtonDisplayMode: 'minimal',
            }}
          >
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="(auth)" options={{ headerShown: false }} />
            <Stack.Screen
              name="map"
              options={{
                headerTitle: '知识地图',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="path"
              options={{
                headerTitle: '学习路径',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="feynman"
              options={{
                headerTitle: '费曼复述',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="exam"
              options={{
                headerTitle: '考试',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="search"
              options={{
                headerTitle: '知识搜索',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="textbook/index"
              options={{
                headerTitle: '电子教材',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="textbook/[sectionId]"
              options={{
                headerTitle: '章节详情',
                headerBackTitle: '电子教材',
              }}
            />
            <Stack.Screen
              name="knowledge/[id]"
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="node/[id]"
              options={{
                headerTitle: '',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="case/[sessionId]/chat"
              options={{
                headerTitle: '病例模拟',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="case/[sessionId]/diagnose"
              options={{
                headerTitle: '提交诊断',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="case/[sessionId]/treat"
              options={{
                headerTitle: '治疗方案',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="case/[sessionId]/score"
              options={{
                headerTitle: '评分报告',
                headerBackTitle: '返回',
              }}
            />
            <Stack.Screen
              name="ai-chat"
              options={{ headerShown: false }}
            />
          </Stack>
          </ErrorBoundary>
        </AuthGuard>
      </AuthProvider>
    </QueryClientProvider>
  )
}

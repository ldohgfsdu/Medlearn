import { Redirect } from 'expo-router';

/**
 * 根路径重定向
 * 引导用户进入主标签页或由 RootLayout 的 AuthGuard 处理登录跳转
 */
export default function Index() {
  return <Redirect href="/(tabs)" />;
}

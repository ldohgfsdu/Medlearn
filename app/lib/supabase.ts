import 'react-native-url-polyfill/auto'
import { createClient, SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY

const hasSupabaseConfig = Boolean(supabaseUrl && supabaseAnonKey)

export const supabase: SupabaseClient | null = hasSupabaseConfig
  ? createClient(supabaseUrl!, supabaseAnonKey!)
  : null

export const isSupabaseEnabled = hasSupabaseConfig

// Demo 阶段：如果没有配置，返回一个不会报错的空对象
export const getSupabase = () => supabase
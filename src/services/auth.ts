/**
 * 认证服务
 * 替代微信登录，使用 Supabase Auth
 */

import {
  supabase,
  signInWithEmail,
  signUpWithEmail,
  signInAnonymously,
  signOut,
  getCurrentUser,
  getCurrentSession,
  onAuthStateChange,
} from '../lib/supabase/client'
import type { UserProfile } from '../lib/supabase/types'

export interface AuthResult {
  success: boolean
  user?: any
  error?: string
  isNewUser?: boolean
}

/**
 * 认证服务类
 */
export class AuthService {
  /**
   * 邮箱密码登录
   */
  static async loginWithEmail(email: string, password: string): Promise<AuthResult> {
    try {
      const { data, error } = await signInWithEmail(email, password)

      if (error) {
        return {
          success: false,
          error: error.message,
        }
      }

      return {
        success: true,
        user: data.user,
        isNewUser: false,
      }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '登录失败',
      }
    }
  }

  /**
   * 邮箱注册
   */
  static async registerWithEmail(
    email: string,
    password: string,
    nickname?: string
  ): Promise<AuthResult> {
    try {
      const { data, error } = await signUpWithEmail(email, password, nickname)

      if (error) {
        return {
          success: false,
          error: error.message,
        }
      }

      return {
        success: true,
        user: data.user,
        isNewUser: true,
      }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '注册失败',
      }
    }
  }

  /**
   * 匿名登录（游客模式）
   */
  static async loginAsGuest(): Promise<AuthResult> {
    try {
      const { data, error } = await signInAnonymously()

      if (error) {
        return {
          success: false,
          error: error.message,
        }
      }

      return {
        success: true,
        user: data.user,
        isNewUser: true,
      }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '游客登录失败',
      }
    }
  }

  /**
   * 退出登录
   */
  static async logout(): Promise<{ success: boolean; error?: string }> {
    try {
      const { error } = await signOut()

      if (error) {
        return {
          success: false,
          error: error.message,
        }
      }

      return { success: true }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '退出失败',
      }
    }
  }

  /**
   * 获取当前用户
   */
  static async getUser() {
    return await getCurrentUser()
  }

  /**
   * 获取当前会话
   */
  static async getSession() {
    return await getCurrentSession()
  }

  /**
   * 获取用户资料
   */
  static async getUserProfile(userId: string): Promise<UserProfile | null> {
    try {
      const { data, error } = await supabase
        .from('user_profiles')
        .select('*')
        .eq('id', userId)
        .single()

      if (error) {
        console.error('获取用户资料失败:', error)
        return null
      }

      return data
    } catch (err) {
      console.error('获取用户资料异常:', err)
      return null
    }
  }

  /**
   * 更新用户资料
   */
  static async updateUserProfile(
    userId: string,
    updates: Partial<UserProfile>
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const { error } = await supabase
        .from('user_profiles')
        .update(updates)
        .eq('id', userId)

      if (error) {
        return {
          success: false,
          error: error.message,
        }
      }

      return { success: true }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '更新失败',
      }
    }
  }

  /**
   * 监听认证状态变化
   */
  static onAuthChange(callback: (event: string, session: any) => void) {
    return onAuthStateChange(callback)
  }

  /**
   * 检查是否已登录
   */
  static async isLoggedIn(): Promise<boolean> {
    const user = await getCurrentUser()
    return !!user
  }

  /**
   * 获取用户 ID
   */
  static async getUserId(): Promise<string | null> {
    const user = await getCurrentUser()
    return user?.id || null
  }
}

export default AuthService
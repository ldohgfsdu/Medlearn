import { useState } from 'react'
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native'
import { useRouter, Link } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '@/hooks/useAuth'
import { Colors, Typography, Spacing, BorderRadius, Shadows, FontFamily } from '@/constants/theme'

export default function LoginScreen() {
  const router = useRouter()
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async () => {
    setError('')
    if (!email.trim() || !password.trim()) {
      setError('请输入邮箱和密码')
      return
    }
    try {
      setLoading(true)
      setError('')
      const { error: err } = await signIn(email.trim(), password)
      if (err) {
        // 将英文错误信息转为中文
        if (err.includes('Invalid login credentials')) {
          setError('邮箱或密码不正确，请重试')
        } else if (err.includes('Email not confirmed')) {
          setError('邮箱尚未验证，请先验证邮箱')
        } else if (err.includes('Too many requests')) {
          setError('登录尝试过于频繁，请稍后再试')
        } else {
          setError(err)
        }
      } else {
        router.replace('/(tabs)')
      }
    } catch {
      setError('网络错误，请检查连接后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <View style={styles.logoWrap}>
            <View style={styles.logoMonogram}>
              <Text style={styles.logoLetter}>M</Text>
            </View>
          </View>
          <Text style={styles.eyebrow}>Clinical Learning Studio</Text>
          <Text style={styles.title}>MedLearn</Text>
          <Text style={styles.subtitle}>结构化医学知识与临床思维训练</Text>
        </View>

        <View style={styles.form}>
          <View style={styles.inputWrap}>
            <Ionicons name="mail-outline" size={18} color={Colors.neutral[400]} style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="邮箱地址"
              placeholderTextColor={Colors.textTertiary}
              value={email}
              onChangeText={(t) => { setEmail(t); setError('') }}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>
          <View style={styles.inputWrap}>
            <Ionicons name="lock-closed-outline" size={18} color={Colors.neutral[400]} style={styles.inputIcon} />
            <TextInput
              style={styles.input}
              placeholder="密码"
              placeholderTextColor={Colors.textTertiary}
              value={password}
              onChangeText={(t) => { setPassword(t); setError('') }}
              secureTextEntry={!showPassword}
            />
            <TouchableOpacity
              onPress={() => setShowPassword(!showPassword)}
              style={styles.eyeBtn}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Ionicons
                name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                size={18}
                color={Colors.neutral[400]}
              />
            </TouchableOpacity>
          </View>

          {error ? (
            <View style={styles.errorWrap}>
              <Ionicons name="alert-circle" size={16} color={Colors.error} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          <TouchableOpacity
            style={[styles.button, loading && styles.buttonDisabled]}
            onPress={handleLogin}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color={Colors.surface} />
            ) : (
              <Text style={styles.buttonText}>登录</Text>
            )}
          </TouchableOpacity>

          <Link href="/(auth)/register" asChild>
            <TouchableOpacity style={styles.linkButton}>
              <Text style={styles.linkText}>
                还没有账号？<Text style={styles.linkHighlight}>去注册</Text>
              </Text>
            </TouchableOpacity>
          </Link>
        </View>
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    width: '100%',
    maxWidth: 520,
    alignSelf: 'center',
    padding: Spacing['2xl'],
  },
  header: {
    alignItems: 'center',
    marginBottom: Spacing['4xl'],
  },
  logoWrap: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.base,
    ...Shadows.level2,
  },
  logoMonogram: {
    width: 58,
    height: 58,
    borderRadius: 29,
    borderWidth: 1,
    borderColor: 'rgba(231, 220, 201, 0.42)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoLetter: {
    fontSize: 25,
    lineHeight: 30,
    fontWeight: '600',
    color: '#E7DCC9',
    fontFamily: FontFamily.sans,
  },
  eyebrow: {
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '400',
    color: Colors.textTertiary,
    marginBottom: Spacing.xs,
  },
  title: {
    ...Typography.displayMedium,
    color: Colors.textPrimary,
    fontFamily: FontFamily.sans,
  },
  subtitle: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    marginTop: Spacing.xs,
  },
  form: {
    gap: Spacing.md,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    minHeight: 52,
  },
  inputIcon: {
    marginRight: Spacing.sm,
  },
  input: {
    flex: 1,
    ...Typography.bodyLarge,
    color: Colors.textPrimary,
    paddingVertical: Spacing.md,
  },
  eyeBtn: {
    paddingLeft: Spacing.sm,
  },
  errorWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    backgroundColor: Colors.errorBg,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.errorBorder,
  },
  errorText: {
    ...Typography.bodySmall,
    color: Colors.error,
    flex: 1,
  },
  button: {
    backgroundColor: Colors.primary[700],
    borderRadius: BorderRadius.full,
    padding: Spacing.base,
    alignItems: 'center',
    minHeight: 52,
    justifyContent: 'center',
    marginTop: Spacing.sm,
    ...Shadows.level1,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    ...Typography.labelLarge,
    color: Colors.surface,
    fontSize: 16,
    fontWeight: '500',
  },
  linkButton: {
    alignItems: 'center',
    padding: Spacing.base,
  },
  linkText: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
  },
  linkHighlight: {
    color: Colors.primary[700],
    fontWeight: '600',
  },
})

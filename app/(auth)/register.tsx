import { useEffect, useState } from 'react'
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  ScrollView,
} from 'react-native'
import { Link, useRouter } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'
import { useAuth } from '@/hooks/useAuth'
import { Colors, Typography, Spacing, BorderRadius, Shadows } from '@/constants/theme'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const RESEND_SECONDS = 60

function authErrorMessage(error: string): string {
  if (error.includes('already registered') || error.includes('already been registered')) {
    return '该邮箱已经注册，请直接登录'
  }
  if (error.includes('rate limit') || error.includes('Too many requests')) {
    return '操作过于频繁，请稍后再试'
  }
  if (error.includes('Token has expired')) {
    return '验证码已过期，请重新发送'
  }
  if (error.includes('Token') || error.includes('invalid')) {
    return '验证码不正确，请检查后重试'
  }
  return error
}

export default function RegisterScreen() {
  const router = useRouter()
  const { signUp, verifySignUpCode, resendSignUpCode } = useAuth()
  const [step, setStep] = useState<'details' | 'verification'>('details')
  const [nickname, setNickname] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setInterval(() => {
      setCountdown((current) => Math.max(0, current - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [countdown])

  const validateDetails = () => {
    if (!nickname.trim() || !email.trim() || !password || !confirmPassword) {
      return '请填写所有必填项'
    }
    if (!EMAIL_PATTERN.test(email.trim())) {
      return '请输入有效的邮箱地址'
    }
    if (password.length < 8) {
      return '密码至少需要 8 位'
    }
    if (password !== confirmPassword) {
      return '两次输入的密码不一致'
    }
    return ''
  }

  const handleSendCode = async () => {
    const validationError = validateDetails()
    if (validationError) {
      setError(validationError)
      return
    }

    try {
      setError('')
      setLoading(true)
      const normalizedEmail = email.trim().toLowerCase()
      const { error: signUpError } = await signUp(normalizedEmail, password, nickname.trim())

      if (signUpError) {
        setError(authErrorMessage(signUpError))
        return
      }

      setEmail(normalizedEmail)
      setStep('verification')
      setCountdown(RESEND_SECONDS)
    } catch (e) {
      setError('网络错误，请检查连接后重试')
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async () => {
    if (!/^\d{6}$/.test(code)) {
      setError('请输入邮件中的 6 位验证码')
      return
    }

    try {
      setError('')
      setLoading(true)
      const { error: verifyError } = await verifySignUpCode(email, code)

      if (verifyError) {
        setError(authErrorMessage(verifyError))
        return
      }

      router.replace('/(tabs)')
    } catch (e) {
      setError('网络错误，请检查连接后重试')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    if (countdown > 0 || resending) return
    try {
      setError('')
      setResending(true)
      const { error: resendError } = await resendSignUpCode(email)

      if (resendError) {
        setError(authErrorMessage(resendError))
        return
      }
      setCountdown(RESEND_SECONDS)
    } catch (e) {
      setError('网络错误，请检查连接后重试')
    } finally {
      setResending(false)
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <View style={styles.logoWrap}>
            <Ionicons name="school-outline" size={38} color={Colors.primary[500]} />
          </View>
          <Text style={styles.title}>
            {step === 'details' ? '创建账号' : '验证邮箱'}
          </Text>
          <Text style={styles.subtitle}>
            {step === 'details'
              ? '开始你的临床推理训练'
              : `验证码已发送至 ${email}`}
          </Text>
        </View>

        <View style={styles.form}>
          {step === 'details' ? (
            <>
              <View style={styles.inputWrap}>
                <Ionicons name="person-outline" size={19} color={Colors.neutral[400]} />
                <TextInput
                  style={styles.input}
                  placeholder="昵称"
                  placeholderTextColor={Colors.textTertiary}
                  value={nickname}
                  onChangeText={(value) => {
                    setNickname(value)
                    setError('')
                  }}
                  maxLength={30}
                />
              </View>

              <View style={styles.inputWrap}>
                <Ionicons name="mail-outline" size={19} color={Colors.neutral[400]} />
                <TextInput
                  style={styles.input}
                  placeholder="电子邮箱"
                  placeholderTextColor={Colors.textTertiary}
                  value={email}
                  onChangeText={(value) => {
                    setEmail(value)
                    setError('')
                  }}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  textContentType="emailAddress"
                />
              </View>

              <View style={styles.inputWrap}>
                <Ionicons name="lock-closed-outline" size={19} color={Colors.neutral[400]} />
                <TextInput
                  style={styles.input}
                  placeholder="密码（至少 8 位）"
                  placeholderTextColor={Colors.textTertiary}
                  value={password}
                  onChangeText={(value) => {
                    setPassword(value)
                    setError('')
                  }}
                  secureTextEntry={!showPassword}
                  textContentType="newPassword"
                />
                <TouchableOpacity onPress={() => setShowPassword((shown) => !shown)}>
                  <Ionicons
                    name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                    size={20}
                    color={Colors.neutral[400]}
                  />
                </TouchableOpacity>
              </View>

              <View style={styles.inputWrap}>
                <Ionicons name="shield-checkmark-outline" size={19} color={Colors.neutral[400]} />
                <TextInput
                  style={styles.input}
                  placeholder="再次输入密码"
                  placeholderTextColor={Colors.textTertiary}
                  value={confirmPassword}
                  onChangeText={(value) => {
                    setConfirmPassword(value)
                    setError('')
                  }}
                  secureTextEntry={!showPassword}
                  textContentType="newPassword"
                />
              </View>
            </>
          ) : (
            <>
              <View style={styles.codeInputWrap}>
                <TextInput
                  style={styles.codeInput}
                  placeholder="000000"
                  placeholderTextColor={Colors.neutral[300]}
                  value={code}
                  onChangeText={(value) => {
                    setCode(value.replace(/\D/g, '').slice(0, 6))
                    setError('')
                  }}
                  keyboardType="number-pad"
                  textContentType="oneTimeCode"
                  maxLength={6}
                  autoFocus
                />
              </View>

              <View style={styles.verificationActions}>
                <TouchableOpacity onPress={() => {
                  setStep('details')
                  setCode('')
                  setError('')
                }}>
                  <Text style={styles.secondaryAction}>修改邮箱</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={handleResend}
                  disabled={countdown > 0 || resending}
                >
                  <Text
                    style={[
                      styles.secondaryAction,
                      (countdown > 0 || resending) && styles.actionDisabled,
                    ]}
                  >
                    {resending
                      ? '发送中...'
                      : countdown > 0
                        ? `${countdown} 秒后重发`
                        : '重新发送'}
                  </Text>
                </TouchableOpacity>
              </View>
            </>
          )}

          {error ? (
            <View style={styles.errorWrap}>
              <Ionicons name="alert-circle-outline" size={17} color={Colors.error} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          <TouchableOpacity
            style={[styles.button, loading && styles.buttonDisabled]}
            onPress={step === 'details' ? handleSendCode : handleVerify}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons
                  name={step === 'details' ? 'mail-outline' : 'checkmark-circle-outline'}
                  size={20}
                  color="#fff"
                />
                <Text style={styles.buttonText}>
                  {step === 'details' ? '发送验证码' : '验证并注册'}
                </Text>
              </>
            )}
          </TouchableOpacity>

          <Link href="/(auth)/login" asChild>
            <TouchableOpacity style={styles.linkButton}>
              <Text style={styles.linkText}>
                已经有账号了？<Text style={styles.linkHighlight}>前往登录</Text>
              </Text>
            </TouchableOpacity>
          </Link>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: Spacing['2xl'],
  },
  header: {
    alignItems: 'center',
    marginBottom: Spacing['2xl'],
  },
  logoWrap: {
    width: 76,
    height: 76,
    borderRadius: 26,
    backgroundColor: Colors.primary[50],
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.base,
    ...Shadows.level2,
  },
  title: {
    ...Typography.titleLarge,
    color: Colors.textPrimary,
    fontSize: 25,
  },
  subtitle: {
    ...Typography.bodyMedium,
    color: Colors.textSecondary,
    marginTop: Spacing.xs,
    textAlign: 'center',
  },
  form: {
    gap: Spacing.md,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    minHeight: 54,
  },
  input: {
    flex: 1,
    ...Typography.bodyLarge,
    color: Colors.textPrimary,
    paddingVertical: Spacing.md,
  },
  codeInputWrap: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    borderWidth: 2,
    borderColor: Colors.primary[200],
    paddingHorizontal: Spacing.lg,
  },
  codeInput: {
    color: Colors.textPrimary,
    fontSize: 32,
    fontWeight: '600',
    letterSpacing: 12,
    textAlign: 'center',
    paddingVertical: Spacing.xl,
  },
  verificationActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.xs,
  },
  secondaryAction: {
    ...Typography.bodyMedium,
    color: Colors.primary[500],
    fontWeight: '600',
  },
  actionDisabled: {
    color: Colors.textTertiary,
  },
  errorWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: '#FECACA',
    backgroundColor: '#FEF2F2',
    padding: Spacing.md,
  },
  errorText: {
    ...Typography.bodySmall,
    color: Colors.error,
    flex: 1,
  },
  button: {
    flexDirection: 'row',
    gap: Spacing.sm,
    backgroundColor: Colors.primary[500],
    borderRadius: BorderRadius.lg,
    padding: Spacing.base,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 54,
    marginTop: Spacing.xs,
    ...Shadows.level1,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    ...Typography.labelLarge,
    color: '#fff',
    fontSize: 16,
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
    color: Colors.primary[500],
    fontWeight: '600',
  },
})

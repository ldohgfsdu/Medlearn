import { useMemo, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useAISettings } from '@/hooks/useAISettings'
import {
  AI_PROVIDER_PRESETS,
  getAISettingsStorageLabel,
  normalizeAISettings,
  type AIProviderPreset,
  type AISettings,
  type EmbeddingProvider,
} from '@/lib/ai-settings'
import { BorderRadius, Colors, Spacing, Typography } from '@/constants/theme'
import { Layout } from '@/constants/layout'

export const options = { headerTitle: 'AI 设置' }

const PROVIDER_OPTIONS: Array<{ id: AIProviderPreset; label: string; note: string }> = [
  { id: 'server', label: '服务端默认', note: '使用 Medlearn 部署的模型与配额' },
  { id: 'deepseek', label: 'DeepSeek', note: '填写你自己的 DeepSeek API Key' },
  { id: 'openai', label: 'OpenAI 兼容', note: 'OpenAI / 硅基流动 / 其他兼容接口' },
  { id: 'custom', label: '自定义', note: '自行填写 Base URL 与模型名' },
]

const EMBED_OPTIONS: Array<{ id: EmbeddingProvider; label: string; note: string }> = [
  { id: 'ollama', label: '本地 Ollama', note: '推荐 bge-m3，用于费曼/RAG 检索' },
  { id: 'proxy', label: '服务端代理', note: '使用远程 embedding-proxy' },
]

function FieldLabel({ children }: { children: string }) {
  return <Text style={styles.fieldLabel}>{children}</Text>
}

export default function AISettingsScreen() {
  const { settings, loading, saving, testing, testResult, save, reset, testConnection } =
    useAISettings()
  const [draft, setDraft] = useState<AISettings | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)

  const activeDraft = useMemo(() => normalizeAISettings(draft ?? settings), [draft, settings])
  const usesCustom = activeDraft.provider !== 'server'
  const storageLabel = getAISettingsStorageLabel()

  const patchDraft = (patch: Partial<AISettings>) => {
    setDraft((current) => normalizeAISettings({ ...(current ?? settings), ...patch }))
  }

  const selectProvider = (provider: AIProviderPreset) => {
    if (provider === 'deepseek' || provider === 'openai') {
      patchDraft({
        provider,
        chatBaseUrl: AI_PROVIDER_PRESETS[provider].chatBaseUrl,
        chatModel: AI_PROVIDER_PRESETS[provider].chatModel,
      })
      return
    }
    patchDraft({ provider })
  }

  const handleSave = async () => {
    try {
      await save(activeDraft)
      setDraft(null)
      Alert.alert('已保存', `配置已写入${storageLabel}，立即生效。`)
    } catch (error) {
      Alert.alert('保存失败', error instanceof Error ? error.message : '请稍后重试')
    }
  }

  const handleReset = () => {
    Alert.alert('恢复默认', '将清除本地 AI 配置并恢复为服务端默认设置。', [
      { text: '取消', style: 'cancel' },
      {
        text: '恢复',
        style: 'destructive',
        onPress: async () => {
          await reset()
          setDraft(null)
        },
      },
    ])
  }

  const handleTest = async () => {
    try {
      await testConnection(activeDraft)
    } catch (error) {
      Alert.alert('连接失败', error instanceof Error ? error.message : '请检查配置')
    }
  }

  if (loading) {
    return (
      <View style={styles.loadingWrap}>
        <ActivityIndicator size="large" color={Colors.primary[600]} />
      </View>
    )
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.heroCard}>
          <View style={styles.heroIcon}>
            <Ionicons name="sparkles" size={22} color={Colors.primary[700]} />
          </View>
          <View style={styles.heroCopy}>
            <Text style={styles.heroTitle}>模型与密钥</Text>
            <Text style={styles.heroText}>
              API Key 仅保存在{storageLabel}，不会上传到 Medlearn 账号。病例患者对话、智能问答、费曼评估都会读取这里的配置。
            </Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>对话模型</Text>
        <View style={styles.card}>
          {PROVIDER_OPTIONS.map((option, index) => {
            const active = activeDraft.provider === option.id
            return (
              <TouchableOpacity
                key={option.id}
                style={[styles.choiceRow, index < PROVIDER_OPTIONS.length - 1 && styles.choiceBorder]}
                onPress={() => selectProvider(option.id)}
                activeOpacity={0.7}
              >
                <View style={[styles.radio, active && styles.radioActive]}>
                  {active && <View style={styles.radioDot} />}
                </View>
                <View style={styles.choiceCopy}>
                  <Text style={styles.choiceLabel}>{option.label}</Text>
                  <Text style={styles.choiceNote}>{option.note}</Text>
                </View>
              </TouchableOpacity>
            )
          })}
        </View>

        {usesCustom && (
          <View style={styles.fieldCard}>
            <FieldLabel>API Key</FieldLabel>
            <View style={styles.secretRow}>
              <TextInput
                style={[styles.input, styles.secretInput]}
                value={activeDraft.chatApiKey}
                onChangeText={(chatApiKey) => patchDraft({ chatApiKey })}
                placeholder="sk-..."
                placeholderTextColor={Colors.textTertiary}
                secureTextEntry={!showApiKey}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <TouchableOpacity
                style={styles.eyeButton}
                onPress={() => setShowApiKey((value) => !value)}
              >
                <Ionicons
                  name={showApiKey ? 'eye-off-outline' : 'eye-outline'}
                  size={20}
                  color={Colors.textSecondary}
                />
              </TouchableOpacity>
            </View>

            <FieldLabel>接口地址 (Base URL)</FieldLabel>
            <TextInput
              style={styles.input}
              value={activeDraft.chatBaseUrl}
              onChangeText={(chatBaseUrl) => patchDraft({ chatBaseUrl })}
              placeholder="https://api.deepseek.com/v1"
              placeholderTextColor={Colors.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <FieldLabel>模型名称</FieldLabel>
            <TextInput
              style={styles.input}
              value={activeDraft.chatModel}
              onChangeText={(chatModel) => patchDraft({ chatModel })}
              placeholder="deepseek-chat"
              placeholderTextColor={Colors.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
            />

            <Text style={styles.helperText}>
              DeepSeek 常用：`deepseek-chat` / `deepseek-reasoner`。OpenAI 兼容服务请填写对应模型 ID。
            </Text>
          </View>
        )}

        <Text style={styles.sectionTitle}>向量检索 (Embedding)</Text>
        <View style={styles.card}>
          {EMBED_OPTIONS.map((option, index) => {
            const active = activeDraft.embeddingProvider === option.id
            return (
              <TouchableOpacity
                key={option.id}
                style={[styles.choiceRow, index < EMBED_OPTIONS.length - 1 && styles.choiceBorder]}
                onPress={() => patchDraft({ embeddingProvider: option.id })}
                activeOpacity={0.7}
              >
                <View style={[styles.radio, active && styles.radioActive]}>
                  {active && <View style={styles.radioDot} />}
                </View>
                <View style={styles.choiceCopy}>
                  <Text style={styles.choiceLabel}>{option.label}</Text>
                  <Text style={styles.choiceNote}>{option.note}</Text>
                </View>
              </TouchableOpacity>
            )
          })}

          {activeDraft.embeddingProvider === 'ollama' && (
            <View style={styles.embedFields}>
              <FieldLabel>Ollama 地址</FieldLabel>
              <TextInput
                style={styles.input}
                value={activeDraft.ollamaUrl}
                onChangeText={(ollamaUrl) => patchDraft({ ollamaUrl })}
                placeholder="http://192.168.x.x:11434"
                placeholderTextColor={Colors.textTertiary}
                autoCapitalize="none"
                autoCorrect={false}
              />
              <Text style={styles.helperText}>
                真机请填电脑局域网 IP，不要用 127.0.0.1。先执行 `ollama pull bge-m3`。
              </Text>

              <FieldLabel>Embedding 模型</FieldLabel>
              <TextInput
                style={styles.input}
                value={activeDraft.ollamaEmbedModel}
                onChangeText={(ollamaEmbedModel) => patchDraft({ ollamaEmbedModel })}
                placeholder="bge-m3"
                placeholderTextColor={Colors.textTertiary}
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>
          )}
        </View>

        {testResult && (
          <View style={styles.testResult}>
            <Ionicons name="information-circle-outline" size={18} color={Colors.primary[700]} />
            <Text style={styles.testResultText}>{testResult}</Text>
          </View>
        )}

        <TouchableOpacity
          style={[styles.primaryButton, (saving || testing) && styles.buttonDisabled]}
          onPress={handleTest}
          disabled={saving || testing}
        >
          {testing ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Ionicons name="pulse-outline" size={18} color="#fff" />
              <Text style={styles.primaryButtonText}>测试连接</Text>
            </>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.saveButton, saving && styles.buttonDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          {saving ? (
            <ActivityIndicator color={Colors.primary[700]} />
          ) : (
            <Text style={styles.saveButtonText}>保存设置</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity style={styles.resetButton} onPress={handleReset} disabled={saving}>
          <Text style={styles.resetButtonText}>恢复默认</Text>
        </TouchableOpacity>
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
    paddingHorizontal: Layout.screenPaddingX,
    paddingBottom: Spacing['3xl'],
    gap: Spacing.md,
  },
  loadingWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background,
  },
  heroCard: {
    flexDirection: 'row',
    gap: Spacing.md,
    backgroundColor: Colors.primary[50],
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.primary[100],
    padding: Spacing.base,
    marginTop: Spacing.sm,
  },
  heroIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroCopy: {
    flex: 1,
  },
  heroTitle: {
    ...Typography.titleSmall,
    color: Colors.primary[800],
    marginBottom: 4,
  },
  heroText: {
    ...Typography.bodySmall,
    color: Colors.primary[900],
    lineHeight: 20,
  },
  sectionTitle: {
    ...Typography.labelLarge,
    color: Colors.textSecondary,
    marginTop: Spacing.sm,
    marginLeft: 4,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    overflow: 'hidden',
  },
  fieldCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.base,
  },
  choiceRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    padding: Spacing.base,
  },
  choiceBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  radio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: Colors.neutral[300],
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  radioActive: {
    borderColor: Colors.primary[600],
  },
  radioDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: Colors.primary[600],
  },
  choiceCopy: {
    flex: 1,
  },
  choiceLabel: {
    ...Typography.titleSmall,
    color: Colors.textPrimary,
  },
  choiceNote: {
    ...Typography.bodySmall,
    color: Colors.textSecondary,
    marginTop: 2,
    lineHeight: 18,
  },
  fieldLabel: {
    ...Typography.labelMedium,
    color: Colors.textSecondary,
    marginBottom: Spacing.xs,
    marginTop: Spacing.sm,
  },
  input: {
    backgroundColor: Colors.neutral[100],
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.base,
    paddingVertical: Spacing.md,
    ...Typography.bodyMedium,
    color: Colors.textPrimary,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  secretRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  secretInput: {
    flex: 1,
  },
  eyeButton: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  helperText: {
    ...Typography.bodySmall,
    color: Colors.textTertiary,
    lineHeight: 18,
    marginTop: Spacing.sm,
  },
  embedFields: {
    paddingHorizontal: Spacing.base,
    paddingBottom: Spacing.base,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  testResult: {
    flexDirection: 'row',
    gap: Spacing.sm,
    alignItems: 'flex-start',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.primary[100],
    padding: Spacing.md,
  },
  testResultText: {
    ...Typography.bodySmall,
    color: Colors.textPrimary,
    flex: 1,
    lineHeight: 20,
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.primary[600],
    borderRadius: BorderRadius.full,
    minHeight: 48,
    marginTop: Spacing.sm,
  },
  saveButton: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.primary[50],
    borderRadius: BorderRadius.full,
    minHeight: 48,
    borderWidth: 1,
    borderColor: Colors.primary[200],
  },
  resetButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  primaryButtonText: {
    ...Typography.labelLarge,
    color: '#fff',
    fontWeight: '700',
  },
  saveButtonText: {
    ...Typography.labelLarge,
    color: Colors.primary[700],
    fontWeight: '700',
  },
  resetButtonText: {
    ...Typography.labelMedium,
    color: Colors.textTertiary,
  },
})
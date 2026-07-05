import { useCallback, useEffect, useState } from 'react'
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native'
import {
  dismissAppDialog,
  registerAppDialog,
  unregisterAppDialog,
  type AppDialogButton,
  type AppDialogConfig,
} from '@/lib/app-dialog'
import { resolveAppDialogButtonStyles } from '@/lib/app-dialog-controller'
import { BorderRadius, Colors, FontFamily, Spacing, Typography } from '@/constants/theme'

const DEFAULT_BUTTONS: AppDialogButton[] = [{ text: '好', style: 'default' }]

export function AppDialogProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<AppDialogConfig | null>(null)

  const present = useCallback((next: AppDialogConfig | null) => {
    setConfig(next)
  }, [])

  useEffect(() => {
    registerAppDialog(present)
    return unregisterAppDialog
  }, [present])

  const buttons = config?.buttons?.length ? config.buttons : DEFAULT_BUTTONS
  const singleButton = buttons.length === 1

  const handleDismiss = () => {
    dismissAppDialog()
  }

  const handlePress = (button: AppDialogButton) => {
    const onPress = button.onPress
    dismissAppDialog()
    onPress?.()
  }

  return (
    <>
      {children}
      <Modal
        transparent
        animationType="fade"
        visible={config !== null}
        onRequestClose={handleDismiss}
      >
        <Pressable style={styles.backdrop} onPress={handleDismiss}>
          <Pressable style={styles.card} onPress={(event) => event.stopPropagation()}>
            {config ? (
              <>
                <Text style={styles.title}>{config.title}</Text>
                {config.message ? <Text style={styles.message}>{config.message}</Text> : null}
                <View style={[styles.actions, singleButton && styles.actionsSingle]}>
                  {buttons.map((button) => {
                    const visual = resolveAppDialogButtonStyles(button, singleButton)
                    return (
                      <TouchableOpacity
                        key={button.text}
                        style={[
                          styles.actionButton,
                          visual.buttonVariant === 'primary' && styles.actionButtonPrimary,
                          visual.buttonVariant === 'cancel' && styles.actionButtonCancel,
                          visual.buttonVariant === 'destructive' && styles.actionButtonDestructive,
                          visual.single && styles.actionButtonSingle,
                        ]}
                        activeOpacity={0.74}
                        onPress={() => handlePress(button)}
                      >
                        <Text
                          style={[
                            styles.actionText,
                            visual.textVariant === 'primary' && styles.actionTextPrimary,
                            visual.textVariant === 'cancel' && styles.actionTextCancel,
                            visual.textVariant === 'destructive' && styles.actionTextDestructive,
                          ]}
                        >
                          {button.text}
                        </Text>
                      </TouchableOpacity>
                    )
                  })}
                </View>
              </>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
    </>
  )
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(13, 31, 27, 0.68)',
    justifyContent: 'center',
    padding: Spacing.lg,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius['2xl'],
    padding: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  title: {
    ...Typography.titleLarge,
    fontFamily: FontFamily.sans,
    color: Colors.textPrimary,
  },
  message: {
    ...Typography.bodyMedium,
    fontFamily: FontFamily.sans,
    color: Colors.textSecondary,
    lineHeight: 22,
    marginTop: Spacing.sm,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: Spacing.lg,
  },
  actionsSingle: {
    justifyContent: 'flex-end',
  },
  actionButton: {
    flex: 1,
    minHeight: 48,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionButtonSingle: {
    flex: 0,
    minWidth: 120,
    paddingHorizontal: Spacing.lg,
  },
  actionButtonCancel: {
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  actionButtonPrimary: {
    borderColor: Colors.primary[700],
    backgroundColor: Colors.primary[700],
  },
  actionButtonDestructive: {
    borderColor: Colors.errorBorder,
    backgroundColor: Colors.errorBg,
  },
  actionText: {
    ...Typography.labelMedium,
    fontFamily: FontFamily.sans,
    fontWeight: '600',
  },
  actionTextPrimary: {
    color: Colors.surface,
  },
  actionTextCancel: {
    color: Colors.textSecondary,
  },
  actionTextDestructive: {
    color: Colors.error,
  },
})
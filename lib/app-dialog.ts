import {
  createDialogQueueState,
  dismissVisibleDialog,
  enqueueDialog,
  type AppDialogQueueState,
} from '@/lib/app-dialog-controller'

export type AppDialogButtonStyle = 'default' | 'cancel' | 'destructive'

export type AppDialogButton = {
  text: string
  style?: AppDialogButtonStyle
  onPress?: () => void
}

export type AppDialogConfig = {
  title: string
  message?: string
  buttons?: AppDialogButton[]
}

type AppDialogHandler = (config: AppDialogConfig | null) => void

let showDialog: AppDialogHandler | null = null
let queueState: AppDialogQueueState = createDialogQueueState()

function syncVisibleDialog() {
  showDialog?.(queueState.current)
}

export function registerAppDialog(handler: AppDialogHandler) {
  showDialog = handler
  syncVisibleDialog()
}

export function unregisterAppDialog() {
  showDialog = null
  queueState = createDialogQueueState()
}

export function getAppDialogQueueSnapshot(): AppDialogQueueState {
  return {
    current: queueState.current,
    pending: [...queueState.pending],
  }
}

/** Drop-in replacement for informational and confirmation Alert.alert calls. */
export function appAlert(title: string, message?: string, buttons?: AppDialogButton[]) {
  if (!showDialog) {
    console.warn('[app-dialog] provider not mounted:', title)
    return
  }
  queueState = enqueueDialog(queueState, { title, message, buttons })
  syncVisibleDialog()
}

/** Called by AppDialogProvider after a button press or backdrop dismiss. */
export function dismissAppDialog() {
  queueState = dismissVisibleDialog(queueState)
  syncVisibleDialog()
}

/** Test helper — reset module state between unit tests. */
export function resetAppDialogForTests() {
  showDialog = null
  queueState = createDialogQueueState()
}
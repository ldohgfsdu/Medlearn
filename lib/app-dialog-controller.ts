import type { AppDialogButton, AppDialogConfig } from '@/lib/app-dialog'

export type AppDialogButtonStyle = 'default' | 'cancel' | 'destructive'

export type ResolvedAppDialogButtonStyles = {
  buttonVariant: 'primary' | 'cancel' | 'destructive'
  textVariant: 'primary' | 'cancel' | 'destructive'
  single: boolean
}

export function resolveAppDialogButtonStyles(
  button: AppDialogButton,
  single: boolean,
): ResolvedAppDialogButtonStyles {
  if (button.style === 'destructive') {
    return { buttonVariant: 'destructive', textVariant: 'destructive', single }
  }
  if (button.style === 'cancel') {
    return { buttonVariant: 'cancel', textVariant: 'cancel', single }
  }
  return { buttonVariant: 'primary', textVariant: 'primary', single }
}

export type AppDialogQueueState = {
  current: AppDialogConfig | null
  pending: AppDialogConfig[]
}

export function createDialogQueueState(): AppDialogQueueState {
  return { current: null, pending: [] }
}

/** Enqueue a dialog; if nothing is visible, promote the head immediately. */
export function enqueueDialog(
  state: AppDialogQueueState,
  config: AppDialogConfig,
): AppDialogQueueState {
  if (state.current) {
    return {
      current: state.current,
      pending: [...state.pending, config],
    }
  }
  return {
    current: config,
    pending: state.pending,
  }
}

/** Dismiss the visible dialog and promote the next queued item, if any. */
export function dismissVisibleDialog(state: AppDialogQueueState): AppDialogQueueState {
  if (state.pending.length === 0) {
    return createDialogQueueState()
  }
  const [next, ...pending] = state.pending
  return { current: next, pending }
}
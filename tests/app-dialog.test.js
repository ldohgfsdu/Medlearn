import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'
import { createRequire } from 'node:module'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const { loadTypeScriptModule } = require('./loadTsModule')

const root = path.join(__dirname, '..')
const controller = loadTypeScriptModule(path.join(root, 'lib', 'app-dialog-controller.ts'))
const dialog = loadTypeScriptModule(path.join(root, 'lib', 'app-dialog.ts'))

function read(relativePath) {
  return readFileSync(path.join(root, relativePath), 'utf8')
}

function expectResolved(button, single, expected) {
  const resolved = controller.resolveAppDialogButtonStyles(button, single)
  assert.equal(resolved.buttonVariant, expected.buttonVariant)
  assert.equal(resolved.textVariant, expected.textVariant)
  assert.equal(resolved.single, expected.single)
}

test('resolveAppDialogButtonStyles maps default, cancel, and destructive variants', () => {
  expectResolved({ text: '好' }, true, {
    buttonVariant: 'primary',
    textVariant: 'primary',
    single: true,
  })
  expectResolved({ text: '取消', style: 'cancel' }, false, {
    buttonVariant: 'cancel',
    textVariant: 'cancel',
    single: false,
  })
  expectResolved({ text: '退出', style: 'destructive' }, false, {
    buttonVariant: 'destructive',
    textVariant: 'destructive',
    single: false,
  })
})

test('dialog queue keeps current visible and drains pending dialogs in order', () => {
  dialog.resetAppDialogForTests()
  let visible = null

  dialog.registerAppDialog((config) => {
    visible = config
  })

  dialog.appAlert('第一则')
  assert.equal(visible?.title, '第一则')
  assert.equal(dialog.getAppDialogQueueSnapshot().pending.length, 0)

  dialog.appAlert('第二则')
  assert.equal(visible?.title, '第一则')
  assert.equal(dialog.getAppDialogQueueSnapshot().pending.length, 1)
  assert.equal(dialog.getAppDialogQueueSnapshot().pending[0]?.title, '第二则')

  dialog.dismissAppDialog()
  assert.equal(visible?.title, '第二则')
  assert.equal(dialog.getAppDialogQueueSnapshot().pending.length, 0)

  dialog.dismissAppDialog()
  assert.equal(visible, null)

  dialog.unregisterAppDialog()
  dialog.resetAppDialogForTests()
})

test('button callbacks fire after dismiss, matching AppDialogProvider press order', () => {
  dialog.resetAppDialogForTests()
  const events = []
  let visible = null

  dialog.registerAppDialog((config) => {
    visible = config
  })

  dialog.appAlert('确认', '确定要退出吗？', [
    { text: '取消', style: 'cancel', onPress: () => events.push('cancel') },
    {
      text: '退出',
      style: 'destructive',
      onPress: () => events.push('destructive'),
    },
  ])

  assert.equal(visible?.title, '确认')
  assert.equal(visible?.buttons?.length, 2)

  const destructive = visible.buttons.find((button) => button.text === '退出')
  const onPress = destructive.onPress
  dialog.dismissAppDialog()
  onPress?.()

  assert.deepEqual(events, ['destructive'])
  assert.equal(visible, null)

  dialog.unregisterAppDialog()
  dialog.resetAppDialogForTests()
})

test('cancel button dismisses without running destructive callback', () => {
  dialog.resetAppDialogForTests()
  const events = []
  let visible = null

  dialog.registerAppDialog((config) => {
    visible = config
  })

  dialog.appAlert('退出登录', '确定要退出吗？', [
    { text: '取消', style: 'cancel', onPress: () => events.push('cancel') },
    { text: '退出', style: 'destructive', onPress: () => events.push('destructive') },
  ])

  const cancel = visible.buttons.find((button) => button.text === '取消')
  const onPress = cancel.onPress
  dialog.dismissAppDialog()
  onPress?.()

  assert.deepEqual(events, ['cancel'])
  assert.equal(visible, null)

  dialog.unregisterAppDialog()
  dialog.resetAppDialogForTests()
})

test('app routes use appAlert instead of native Alert.alert', () => {
  const files = [
    'app/(tabs)/profile.tsx',
    'app/settings/ai.tsx',
    'app/(tabs)/cases.tsx',
    'app/case/[sessionId]/chat.tsx',
    'app/case/[sessionId]/score.tsx',
    'app/case/[sessionId]/diagnose.tsx',
    'app/case/[sessionId]/treat.tsx',
    'app/exam.tsx',
    'app/disease/[id].tsx',
  ]

  for (const file of files) {
    const source = read(file)
    assert.doesNotMatch(source, /Alert\.alert\(/, `${file} still uses Alert.alert`)
    assert.match(source, /appAlert\(/, `${file} should use appAlert`)
  }
})

test('AppDialogProvider is mounted at the app root', () => {
  const layout = read('app/_layout.tsx')
  assert.match(layout, /AppDialogProvider/)
  assert.match(layout, /from '@\/components\/AppDialogProvider'/)
})
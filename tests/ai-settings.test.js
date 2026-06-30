import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
}

test('ai settings screen is linked from profile and stores config locally', () => {
  const profile = read('app/(tabs)/profile.tsx')
  const screen = read('app/settings/ai.tsx')
  const storage = read('lib/ai-settings.ts')

  assert.match(profile, /AI 设置/)
  assert.match(profile, /\/settings\/ai/)
  assert.match(screen, /API Key/)
  assert.match(screen, /测试连接/)
  assert.match(storage, /AsyncStorage/)
  assert.match(storage, /@medlearn\/ai-settings/)
})

test('chat runtime supports custom provider and case patient forwards override', () => {
  const runtime = read('services/ai-runtime.ts')
  const casePatient = read('services/case-patient.ts')
  const edge = read('supabase/functions/case-patient/index.ts')

  assert.match(runtime, /invokeDirect/)
  assert.match(runtime, /usesCustomChatProvider/)
  assert.match(casePatient, /ai_override/)
  assert.match(edge, /parseAIOverride/)
})
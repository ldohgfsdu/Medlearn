/**
 * Case Engine - 病例模拟核心引擎
 * 基于 PRD 第 65-69 章
 */

import { supabase } from '@/lib/supabase'
import { intentParser, type Intent, type IntentType } from './intent-parser'
import { CasePhase } from '@/constants/vindicate'
import { trackCaseEvent } from './analytics'
import { requestCasePatientResponse, requestCasePatientTurn } from './case-patient'

// ============================================
// 类型定义
// ============================================

export interface CaseTemplate {
  id: string
  case_code: string
  title: string
  chief_complaint: string
  specialty?: string | null
  difficulty: string
  estimated_minutes?: number
  demographics: Demographics
  is_active: boolean
  review_status: 'draft' | 'reviewed' | 'approved'
}

export interface Demographics {
  age: number
  gender: 'male' | 'female'
  occupation: string
  education: string
  emotion: string
  presentationContext: string
}

export interface RevealedState {
  historyFields: string[]
  examPerformed: string[]
  testsOrdered: string[]
  testsResultsReleased: string[]
}

export interface CaseState {
  caseId: string
  sessionId: string
  currentPhase: CasePhase
  revealed: RevealedState
  turnCount: number
  hintsUsed: number
  maxHints: number
  startedAt: string
}

export interface CaseMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  turnNumber: number
  intentType?: IntentType
  intentTarget?: string
  createdAt: string
}

// ============================================
// State Machine
// ============================================

const VALID_TRANSITIONS: Record<CasePhase, CasePhase[]> = {
  [CasePhase.INTRO]: [CasePhase.HISTORY],
  [CasePhase.HISTORY]: [CasePhase.EXAM, CasePhase.TESTS],
  [CasePhase.EXAM]: [CasePhase.HISTORY, CasePhase.TESTS, CasePhase.DIAGNOSIS],
  [CasePhase.TESTS]: [CasePhase.EXAM, CasePhase.DIAGNOSIS],
  [CasePhase.DIAGNOSIS]: [CasePhase.TREATMENT],
  [CasePhase.TREATMENT]: [CasePhase.SCORING],
  [CasePhase.SCORING]: [CasePhase.FEEDBACK],
  [CasePhase.FEEDBACK]: [],
}

const PHASE_PERMISSIONS: Record<IntentType, CasePhase[]> = {
  ask_history: [CasePhase.INTRO, CasePhase.HISTORY, CasePhase.EXAM],
  physical_exam: [CasePhase.EXAM, CasePhase.HISTORY],
  order_test: [CasePhase.TESTS, CasePhase.EXAM],
  mention_diagnosis: [CasePhase.DIAGNOSIS, CasePhase.EXAM, CasePhase.TESTS],
  mention_treatment: [CasePhase.DIAGNOSIS, CasePhase.TREATMENT],
  phase_transition: [CasePhase.HISTORY, CasePhase.EXAM, CasePhase.TESTS, CasePhase.DIAGNOSIS],
  greeting: [CasePhase.INTRO, CasePhase.HISTORY, CasePhase.EXAM, CasePhase.TESTS],
  off_topic: [CasePhase.INTRO, CasePhase.HISTORY, CasePhase.EXAM, CasePhase.TESTS, CasePhase.DIAGNOSIS],
  empty: [],
  unknown: [CasePhase.INTRO, CasePhase.HISTORY, CasePhase.EXAM, CasePhase.TESTS],
}

const VALID_PHASES = new Set<string>(Object.values(CasePhase))

export function isValidPhase(phase: string): phase is CasePhase {
  return VALID_PHASES.has(phase)
}

export function canTransition(state: CaseState, newPhase: CasePhase): boolean {
  return VALID_TRANSITIONS[state.currentPhase]?.includes(newPhase) ?? false
}

export function canPerformAction(state: CaseState, intentType: IntentType): boolean {
  return PHASE_PERMISSIONS[intentType]?.includes(state.currentPhase) ?? false
}

// ============================================
// Case Engine
// ============================================

export class CaseEngine {
  async startCase(caseId: string, userId: string): Promise<{ sessionId: string; template: CaseTemplate; state: CaseState }> {
    const { data: template, error } = await supabase
      .from('case_templates')
      .select('id,case_code,title,chief_complaint,specialty,difficulty,estimated_minutes,demographics,is_active,review_status')
      .eq('id', caseId)
      .eq('is_active', true)
      .eq('review_status', 'approved')
      .single()

    if (error || !template) {
      throw new Error('病例不存在')
    }

    const { data: session, error: sessionError } = await supabase
      .from('case_sessions')
      .insert({
        user_id: userId,
        case_id: caseId,
        status: 'in_progress',
        current_phase: CasePhase.INTRO,
        revealed: { historyFields: [], examPerformed: [], testsOrdered: [], testsResultsReleased: [] },
      })
      .select()
      .single()

    if (sessionError || !session) {
      throw new Error('创建会话失败')
    }

    // C2 fix: 原子递增
    const { error: rpcError } = await supabase.rpc('increment_usage_count', { p_session_id: session.id })
    if (rpcError) {
      console.warn('[case-engine] increment_usage_count failed, retrying once:', rpcError.message)
      const { error: retryError } = await supabase.rpc('increment_usage_count', {
        p_session_id: session.id,
      })
      if (retryError) {
        console.warn('[case-engine] increment_usage_count retry failed:', retryError.message)
      }
    }

    const state: CaseState = {
      caseId: template.id,
      sessionId: session.id,
      currentPhase: CasePhase.INTRO,
      revealed: { historyFields: [], examPerformed: [], testsOrdered: [], testsResultsReleased: [] },
      turnCount: 0,
      hintsUsed: 0,
      maxHints: 3,
      startedAt: session.started_at,
    }

    await trackCaseEvent({
      eventName: 'case_started',
      userId,
      sessionId: session.id,
      caseId: template.id,
      properties: {
        chiefComplaint: template.chief_complaint,
        difficulty: template.difficulty,
      },
    })

    const { count: completedCount } = await supabase
      .from('case_sessions')
      .select('id', { count: 'exact', head: true })
      .eq('user_id', userId)
      .eq('status', 'completed')
    if ((completedCount ?? 0) > 0) {
      await trackCaseEvent({
        eventName: 'second_case_started',
        userId,
        sessionId: session.id,
        caseId: template.id,
        properties: { completedCasesBeforeStart: completedCount },
      })
    }

    return { sessionId: session.id, template: template as CaseTemplate, state }
  }

  async handleMessage(
    sessionId: string,
    userId: string,
    userMessage: string
  ): Promise<{ response: string; state: CaseState; intent: Intent }> {
    const { state: loadedState, template } = await this.loadContext(sessionId, userId)

    // M9 fix: 创建状态副本，不在原对象上修改
    const state: CaseState = {
      ...loadedState,
      revealed: {
        historyFields: [...loadedState.revealed.historyFields],
        examPerformed: [...loadedState.revealed.examPerformed],
        testsOrdered: [...loadedState.revealed.testsOrdered],
        testsResultsReleased: [...loadedState.revealed.testsResultsReleased],
      },
    }

    const intent = intentParser.parse(userMessage, state.currentPhase)

    if (intent.type !== 'empty' && intent.type !== 'greeting' && intent.type !== 'off_topic') {
      if (!canPerformAction(state, intent.type)) {
        return { response: this.getPhaseRedirectMessage(state.currentPhase), state, intent }
      }
    }

    const eventProps = {
      chiefComplaint: template.chief_complaint,
      difficulty: template.difficulty,
    }
    if (intent.type === 'ask_history' || intent.type === 'unknown') {
      await trackCaseEvent({
        eventName: 'patient_message_sent',
        userId,
        sessionId,
        caseId: template.id,
        ...eventProps,
        properties: { intent: intent.type, target: intent.target },
      })
    }

    let response: string
    let patientResponseSource: 'preset' | 'ai' | null = null
    switch (intent.type) {
      case 'empty':
        response = '请输入你的问题。'
        break
      case 'greeting':
        response = `你好医生！${template.demographics.presentationContext}。`
        if (state.currentPhase === CasePhase.INTRO) {
          state.currentPhase = CasePhase.HISTORY
        }
        break
      case 'off_topic':
        response = '医生，这和我的病有关系吗？'
        break
      case 'ask_history': {
        const resolved = await this.resolveHistoryOrAi(sessionId, userMessage, state, template, intent)
        response = resolved.response
        patientResponseSource = resolved.source
        break
      }
      case 'physical_exam':
        response = await this.handleExamRequest(sessionId, state, intent)
        break
      case 'order_test':
        response = await this.handleTestOrder(sessionId, state, intent)
        break
      case 'mention_diagnosis':
        response = this.handleDiagnosisMention(state, template, intent)
        break
      default:
        this.ensureHistoryPhase(state)
        response = await this.handleUnknownInput(sessionId, userMessage)
        patientResponseSource = 'ai'
        break
    }

    state.turnCount++
    await this.saveState(sessionId, state)
    await this.saveMessage(sessionId, userMessage, response, state.turnCount, intent)

    // 事件追踪
    if ((intent.type === 'ask_history' || intent.type === 'unknown') && patientResponseSource) {
      await trackCaseEvent({
        eventName: 'patient_message_received',
        userId,
        sessionId,
        caseId: template.id,
        ...eventProps,
        properties: { intent: intent.type, source: patientResponseSource, target: intent.target },
      })
    }
    if (intent.type === 'physical_exam') {
      await trackCaseEvent({ eventName: 'exam_requested', userId, sessionId, caseId: template.id, ...eventProps, properties: { region: intent.target } })
    }
    if (intent.type === 'order_test') {
      await trackCaseEvent({ eventName: 'test_ordered', userId, sessionId, caseId: template.id, ...eventProps, properties: { test: intent.target } })
    }

    return { response, state, intent }
  }

  async requestHint(
    sessionId: string,
    userId: string,
  ): Promise<{ hint: string; state: CaseState }> {
    const { state: loadedState, template } = await this.loadContext(sessionId, userId)
    if (loadedState.hintsUsed >= loadedState.maxHints) {
      throw new Error('本病例的提示次数已用完')
    }

    const state: CaseState = {
      ...loadedState,
      revealed: {
        historyFields: [...loadedState.revealed.historyFields],
        examPerformed: [...loadedState.revealed.examPerformed],
        testsOrdered: [...loadedState.revealed.testsOrdered],
        testsResultsReleased: [...loadedState.revealed.testsResultsReleased],
      },
      hintsUsed: loadedState.hintsUsed + 1,
      turnCount: loadedState.turnCount + 1,
    }
    const hintTurn = await requestCasePatientTurn(sessionId, 'hint', { intentType: 'hint' })
    const hint = hintTurn.response
    await this.saveState(sessionId, state)
    const { error: messageError } = await supabase.from('case_messages').insert({
      session_id: sessionId,
      role: 'system',
      content: hint,
      turn_number: state.turnCount,
      intent_type: 'hint',
    })
    if (messageError) {
      console.warn('[case-engine] save hint failed:', messageError.message)
    }
    await trackCaseEvent({
      eventName: 'hint_requested',
      userId,
      sessionId,
      caseId: template.id,
      chiefComplaint: template.chief_complaint,
      difficulty: template.difficulty,
      properties: {
        hintsUsed: state.hintsUsed,
        maxHints: state.maxHints,
        suggestedField: hintTurn.revealed?.hintFieldId ?? null,
      },
    })

    return { hint, state }
  }

  private ensureHistoryPhase(state: CaseState): void {
    if (state.currentPhase === CasePhase.INTRO) {
      state.currentPhase = CasePhase.HISTORY
    }
  }

  private async resolveHistoryOrAi(
    sessionId: string,
    userMessage: string,
    state: CaseState,
    _template: CaseTemplate,
    intent: Intent,
  ): Promise<{ response: string; source: 'preset' | 'ai' }> {
    const turn = await requestCasePatientTurn(sessionId, userMessage, {
      intentType: 'ask_history',
      target: intent.target,
    })
    const historyFieldId = turn.revealed?.historyFieldId
    if (historyFieldId && !state.revealed.historyFields.includes(historyFieldId)) {
      state.revealed.historyFields.push(historyFieldId)
    }
    this.ensureHistoryPhase(state)
    return { response: turn.response, source: turn.source === 'preset' ? 'preset' : 'ai' }
  }

  private async handleExamRequest(sessionId: string, state: CaseState, intent: Intent): Promise<string> {
    const region = intent.target
    if (!region) return '医生，您想检查什么？'

    const turn = await requestCasePatientTurn(sessionId, region, {
      intentType: 'physical_exam',
      target: region,
    })
    const examId = turn.revealed?.examId ?? region
    if (!state.revealed.examPerformed.includes(examId)) {
      state.revealed.examPerformed.push(examId)
    }
    if (state.currentPhase === CasePhase.HISTORY) {
      state.currentPhase = CasePhase.EXAM
    }

    return turn.response
  }

  private async handleTestOrder(sessionId: string, state: CaseState, intent: Intent): Promise<string> {
    const testId = intent.target
    if (!testId) return '医生，您想开什么检查？'

    const turn = await requestCasePatientTurn(sessionId, testId, {
      intentType: 'order_test',
      target: testId,
    })
    const revealedTestId = turn.revealed?.testId ?? testId
    if (!state.revealed.testsOrdered.includes(revealedTestId)) {
      state.revealed.testsOrdered.push(revealedTestId)
    }
    if (!state.revealed.testsResultsReleased.includes(revealedTestId)) {
      state.revealed.testsResultsReleased.push(revealedTestId)
    }
    if (state.currentPhase === CasePhase.EXAM || state.currentPhase === CasePhase.HISTORY) {
      state.currentPhase = CasePhase.TESTS
    }

    return turn.response
  }

  private handleDiagnosisMention(state: CaseState, _template: CaseTemplate, _intent: Intent): string {
    // Only allow diagnosis transition from phases where mention_diagnosis is permitted
    // (mirrors PHASE_PERMISSIONS.mention_diagnosis: EXAM, TESTS, DIAGNOSIS)
    const DIAGNOSIS_ALLOWED_PHASES = [CasePhase.EXAM, CasePhase.TESTS, CasePhase.DIAGNOSIS]
    if (DIAGNOSIS_ALLOWED_PHASES.includes(state.currentPhase)) {
      state.currentPhase = CasePhase.DIAGNOSIS
    }
    return '好的医生，请在诊断页面提交您的正式诊断。'
  }

  private async handleUnknownInput(sessionId: string, input: string): Promise<string> {
    try {
      return await requestCasePatientResponse(sessionId, input)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      if (/network|fetch|timeout|failed|unavailable|503|502|504/i.test(message)) {
        console.warn('[case-engine] case-patient unavailable:', message)
        return '患者暂时无法回应，请稍后重试，或换一种更具体的问法。'
      }
      console.warn('[case-engine] case-patient rejected input:', message)
      return '医生，请把问题说得更具体一些，例如询问疼痛时间、性质、伴随症状或既往病史。'
    }
  }

  private getPhaseRedirectMessage(currentPhase: CasePhase): string {
    switch (currentPhase) {
      case CasePhase.HISTORY:
        return '医生，您还需要继续问病史，或者可以开始查体了。'
      case CasePhase.EXAM:
        return '医生，您可以继续查体，或者开检查，或者提交诊断。'
      case CasePhase.TESTS:
        return '医生，您可以继续开检查，或者提交诊断。'
      case CasePhase.DIAGNOSIS:
        return '请提交您的诊断。'
      case CasePhase.INTRO:
        return '请先问候患者，然后询问症状、病史或哪里不舒服。'
      default:
        return '请按流程操作。'
    }
  }

  private async loadContext(sessionId: string, userId: string): Promise<{ state: CaseState; template: CaseTemplate }> {
    const { data: session, error } = await supabase
      .from('case_sessions')
      .select('*')
      .eq('id', sessionId)
      .eq('user_id', userId)
      .single()

    if (error || !session) {
      throw new Error('会话不存在')
    }

    const { data: template } = await supabase
      .from('case_templates')
      .select('id,case_code,title,chief_complaint,specialty,difficulty,estimated_minutes,demographics,is_active,review_status')
      .eq('id', session.case_id)
      .eq('is_active', true)
      .eq('review_status', 'approved')
      .single()

    if (!template) {
      throw new Error('病例模板不存在')
    }

    // M10 fix: 验证 phase 值
    const phase = isValidPhase(session.current_phase) ? session.current_phase : CasePhase.INTRO

    const state: CaseState = {
      caseId: session.case_id,
      sessionId: session.id,
      currentPhase: phase,
      revealed: session.revealed || {
        historyFields: [],
        examPerformed: [],
        testsOrdered: [],
        testsResultsReleased: [],
      },
      turnCount: session.turn_count || 0,
      hintsUsed: session.hints_used || 0,
      maxHints: session.max_hints || 3,
      startedAt: session.started_at,
    }

    return { state, template: template as CaseTemplate }
  }

  private async saveState(sessionId: string, state: CaseState): Promise<void> {
    const { error } = await supabase
      .from('case_sessions')
      .update({
        current_phase: state.currentPhase,
        revealed: state.revealed,
        turn_count: state.turnCount,
        hints_used: state.hintsUsed,
      })
      .eq('id', sessionId)

    if (error) {
      console.error('[case-engine] saveState failed:', error.message)
      throw new Error('保存进度失败，请重试')
    }
  }

  private async saveMessage(
    sessionId: string,
    userMessage: string,
    assistantResponse: string,
    turnNumber: number,
    intent: Intent
  ): Promise<void> {
    const { error } = await supabase.from('case_messages').insert([
      {
        session_id: sessionId,
        role: 'user',
        content: userMessage,
        turn_number: turnNumber,
        intent_type: intent.type,
        intent_target: intent.target,
        intent_confidence: intent.confidence,
      },
      {
        session_id: sessionId,
        role: 'assistant',
        content: assistantResponse,
        turn_number: turnNumber,
      },
    ])

    if (error) {
      console.error('[case-engine] saveMessage failed:', error.message)
      throw new Error('消息保存失败，请重试')
    }
  }
}

export const caseEngine = new CaseEngine()

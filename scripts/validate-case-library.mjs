import { createClient } from '@supabase/supabase-js'
import { validateCaseQuality } from '../shared/case-quality.ts'

const url = process.env.SUPABASE_URL
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY

if (!url || !serviceRoleKey) {
  console.error('缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY')
  process.exitCode = 2
} else {
  const supabase = createClient(url, serviceRoleKey, {
    auth: { persistSession: false },
  })
  const { data, error } = await supabase
    .from('case_templates')
    .select(
      'id,case_code,title,chief_complaint,difficulty,demographics,patient_world,ground_truth,scoring_rubric,is_active,review_status,reviewed_by,reviewed_at',
    )
    .order('case_code')

  if (error) {
    console.error(`读取病例失败：${error.message}`)
    process.exitCode = 2
  } else {
    let errorCount = 0
    let warningCount = 0
    let approvedCount = 0

    for (const record of data ?? []) {
      if (record.review_status === 'approved') approvedCount += 1
      const issues = validateCaseQuality(record)
      for (const issue of issues) {
        if (issue.severity === 'error') errorCount += 1
        else warningCount += 1
        console.log(
          `${issue.severity.toUpperCase()} ${record.case_code} ${issue.path}: ${issue.message}`,
        )
      }
    }

    console.log(
      `病例总数 ${(data ?? []).length}，已批准 ${approvedCount}，错误 ${errorCount}，警告 ${warningCount}`,
    )
    if (approvedCount < 15) {
      console.error(`ERROR 发布门槛要求 15 个已批准病例，当前为 ${approvedCount}`)
      errorCount += 1
    }
    if (errorCount > 0) process.exitCode = 1
  }
}

export interface CaseTemplateApprovalFields {
  is_active?: boolean | null
  review_status?: string | null
}

export function isApprovedActiveCaseTemplate(
  template: CaseTemplateApprovalFields | null | undefined,
): template is CaseTemplateApprovalFields & { is_active: true; review_status: 'approved' } {
  return template?.is_active === true && template.review_status === 'approved'
}

export function rejectUnapprovedCaseTemplate(
  template: CaseTemplateApprovalFields | null | undefined,
): Response | null {
  if (!template) {
    return new Response(JSON.stringify({ error: 'Case template is unavailable' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  if (template.is_active !== true || template.review_status !== 'approved') {
    return new Response(JSON.stringify({ error: 'Case is not approved for training' }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  return null
}
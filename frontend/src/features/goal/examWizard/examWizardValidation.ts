/** 資格ウィザードの各ステップで「次へ」を許可するかどうかの判定（CODING_RULES.md
 * 「フロントの分岐は.tsへ切り出す」）。activate時に科目・教材が1件以上必要という
 * バックエンドの制約（goal_service.activate_goal）を、ウィザードの途中で早めに伝える。 */
import type { ExamMaterialDraft, ExamSubjectDraft } from './examWizardDrafts'

export function isSubjectDraftValid(draft: ExamSubjectDraft): boolean {
  if (draft.name.trim() === '') {
    return false
  }
  if (draft.examDateType === 'RANGE') {
    return draft.examDateFrom !== '' && draft.examDateTo !== ''
  }
  return draft.examDateFixed !== ''
}

export function canProceedFromSubjects(subjects: ExamSubjectDraft[]): boolean {
  return subjects.length > 0 && subjects.every(isSubjectDraftValid)
}

export function isMaterialDraftValid(draft: ExamMaterialDraft): boolean {
  return (
    draft.name.trim() !== '' &&
    draft.unitLabel.trim() !== '' &&
    draft.totalAmount.trim() !== '' &&
    Number(draft.totalAmount) >= 0 &&
    draft.subjectNames.length > 0
  )
}

export function canProceedFromMaterials(materials: ExamMaterialDraft[]): boolean {
  return materials.length > 0 && materials.every(isMaterialDraftValid)
}

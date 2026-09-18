/** 資格ウィザードのステップ2・3で編集する下書きの型と組み立て関数。
 *
 * テンプレートの科目・教材は名前で対応付ける（`ExamTemplateMaterial.subject_names`と同じ
 * 方式）。実際のIDはステップ2で科目を作成した後にサーバから採番されるため、教材の
 * ペイロード組み立て時に名前→IDのマップで解決する。科目名を後から変更すると対応が
 * 外れる制約があるが、1試験内で科目名が重複することは通常無いため許容している。
 *
 * ウィザードでは合格基準を百分率（PERCENTAGE）のみ扱う（テンプレートは全て百分率で
 * 統一済み）。素点方式が必要な場合は目標詳細画面（試験科目タブ）から後で変更できる。 */
import type { ExamTemplateMaterial, ExamTemplateSubject } from '../../../api/examTemplates'
import type { MaterialCreate, SubjectCreate } from '../../../api/goals'
import type { ExamDateType } from '../subjectOptions'

export type ExamSubjectDraft = {
  name: string
  passingScore: string
  examDateType: ExamDateType
  examDateFrom: string
  examDateTo: string
  examDateFixed: string
}

export type ExamMaterialDraft = {
  name: string
  unitLabel: string
  totalAmount: string
  plannedCycles: string
  subjectNames: string[]
}

export function subjectDraftFromTemplate(subject: ExamTemplateSubject): ExamSubjectDraft {
  return {
    name: subject.name,
    passingScore: String(subject.passing_score),
    examDateType: 'RANGE',
    examDateFrom: '',
    examDateTo: '',
    examDateFixed: '',
  }
}

export function emptySubjectDraft(): ExamSubjectDraft {
  return {
    name: '',
    passingScore: '60',
    examDateType: 'RANGE',
    examDateFrom: '',
    examDateTo: '',
    examDateFixed: '',
  }
}

export function materialDraftFromTemplate(material: ExamTemplateMaterial): ExamMaterialDraft {
  return {
    name: material.name,
    unitLabel: material.unit_label,
    totalAmount: String(material.total_amount),
    plannedCycles: String(material.planned_cycles),
    subjectNames: [...material.subject_names],
  }
}

export function emptyMaterialDraft(): ExamMaterialDraft {
  return { name: '', unitLabel: '', totalAmount: '', plannedCycles: '1', subjectNames: [] }
}

export function buildSubjectCreatePayload(draft: ExamSubjectDraft): SubjectCreate {
  return {
    name: draft.name,
    exam_date_type: draft.examDateType,
    exam_date_from: draft.examDateType === 'RANGE' ? draft.examDateFrom || null : null,
    exam_date_to: draft.examDateType === 'RANGE' ? draft.examDateTo || null : null,
    exam_date_fixed: draft.examDateType === 'FIXED' ? draft.examDateFixed || null : null,
    passing_score_type: 'PERCENTAGE',
    passing_score: draft.passingScore === '' ? null : Number(draft.passingScore),
  }
}

export function buildMaterialCreatePayload(
  draft: ExamMaterialDraft,
  subjectIdByName: Record<string, number>,
  startDate: string,
): MaterialCreate {
  const subjectIds = draft.subjectNames
    .map((name) => subjectIdByName[name])
    .filter((id): id is number => id !== undefined)
  return {
    name: draft.name,
    unit_label: draft.unitLabel,
    total_amount: Number(draft.totalAmount),
    planned_cycles: draft.plannedCycles === '' ? 1 : Number(draft.plannedCycles),
    subject_ids: subjectIds,
    start_date: startDate,
    // 必要連続時間・必要環境・品質指標の方式は、ウィザードでは既定値のまま扱い、
    // 目標詳細画面から後で変更できる（仕様書「資格モードの作成ウィザード」）。
    // due_date_is_manual=falseにより、締切は直前のステップで登録した科目の受験日から
    // サーバ側が自動導出する。
    due_date_is_manual: false,
    required_environment: 'ANY',
    quality_metric_type: 'NONE',
  }
}

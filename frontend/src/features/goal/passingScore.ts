import { t } from '../../locales/t'
import type { SubjectRead } from '../../api/goals'
import type { components } from '../../types/api.d.ts'

export type PassingScoreType = components['schemas']['PassingScoreType']

type PassingScoreSource = Pick<
  SubjectRead,
  'passing_score' | 'passing_score_type' | 'passing_score_max'
>

export type PassingScoreFormState = {
  type: PassingScoreType
  percentValue: string
  rawScoreValue: string
  rawMaxValue: string
}

export type PassingScorePayload = {
  passing_score: number | null
  passing_score_type: PassingScoreType
  passing_score_max: number | null
}

/** 科目フォームの合格点入力欄の初期状態を組み立てる（新規追加時はsubject省略）。 */
export function initPassingScoreFormState(subject?: PassingScoreSource): PassingScoreFormState {
  const type = subject?.passing_score_type ?? 'PERCENTAGE'
  const score = subject?.passing_score ?? null
  const max = subject?.passing_score_max ?? null
  return {
    type,
    percentValue: type === 'PERCENTAGE' && score !== null ? String(score) : '',
    rawScoreValue: type === 'RAW_SCORE' && score !== null ? String(score) : '',
    rawMaxValue: type === 'RAW_SCORE' && max !== null ? String(max) : '',
  }
}

/** フォーム状態からAPI送信用ペイロードを組み立てる（入力方式に応じてpassing_score系3項目を確定させる）。 */
export function buildPassingScorePayload(state: PassingScoreFormState): PassingScorePayload {
  if (state.type === 'RAW_SCORE') {
    return {
      passing_score: state.rawScoreValue === '' ? null : Number(state.rawScoreValue),
      passing_score_type: 'RAW_SCORE',
      passing_score_max: state.rawMaxValue === '' ? null : Number(state.rawMaxValue),
    }
  }
  return {
    passing_score: state.percentValue === '' ? null : Number(state.percentValue),
    passing_score_type: 'PERCENTAGE',
    passing_score_max: null,
  }
}

/** 一覧カードでの合格点表示テキストを組み立てる。未設定の場合はnull。 */
export function formatPassingScoreDisplay(subject: PassingScoreSource): string | null {
  if (subject.passing_score === null || subject.passing_score === undefined) {
    return null
  }
  if (subject.passing_score_type === 'RAW_SCORE' && subject.passing_score_max) {
    return t('goals.subjects.passingScoreDisplay.raw', {
      score: subject.passing_score,
      max: subject.passing_score_max,
    })
  }
  return t('goals.subjects.passingScoreDisplay.percentage', { score: subject.passing_score })
}

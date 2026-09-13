import type { DailyRecordRead } from '../../api/records'

export type CategoryPresence = {
  hasExamCategory: boolean
  hasReadingCategory: boolean
  hasWorkCategory: boolean
}

export type CategoryReportedState = {
  isExamReported: boolean
  isReadingReported: boolean
  isWorkReported: boolean
}

/**
 * その日操作すべき全カテゴリ（hasExamCategory等、ACTIVEな目標の有無で判定）が確定済みかを
 * 判定する（DailyReportPage: 全カテゴリ確定後にダッシュボードへ遷移する判定、および
 * 閲覧画面への初期リダイレクト判定で共有する。仕様変更2026-09-05）。
 *
 * 判定にはカテゴリの「存在」（hasExamCategory等）を使い、「現在選択中のタブとして
 * 表示しているか」（showExamSection等）は使わない。show*Sectionは選択中でないタブでは
 * 常にfalseになるため、これで判定すると「今見ていないカテゴリ」を「対象外」と誤判定し、
 * 1カテゴリ確定しただけで（他カテゴリが未確定でも）全カテゴリ確定済みとみなしてしまう
 * （実ブラウザ確認で発見した不具合、2026-09-05）。
 */
export function isAllCategoriesReported(
  presence: CategoryPresence,
  state: CategoryReportedState,
): boolean {
  const hasAnyCategory =
    presence.hasExamCategory || presence.hasReadingCategory || presence.hasWorkCategory
  if (!hasAnyCategory) {
    return false
  }
  return (
    (!presence.hasExamCategory || state.isExamReported) &&
    (!presence.hasReadingCategory || state.isReadingReported) &&
    (!presence.hasWorkCategory || state.isWorkReported)
  )
}

/**
 * 日次記録からカテゴリ別の確定状況を取り出す（DailyReportPage: 未保存入力の判定・閲覧画面への
 * 転送判定・確定直後の遷移判定の3箇所で同じ変換が必要なため共通化する。CODING_RULES.md
 * 「①DRYの原則」）。
 *
 * 記録を未取得（undefined）の間は「どのカテゴリも未確定」として扱う。取得前に確定済みと
 * みなすと、未確定のカテゴリの入力欄が一瞬だけ読み取り専用として描画されてしまう。
 */
export function toCategoryReportedState(
  record: DailyRecordRead | undefined,
): CategoryReportedState {
  return {
    isExamReported: record?.exam_record_state === 'REPORTED',
    isReadingReported: record?.reading_record_state === 'REPORTED',
    isWorkReported: record?.work_record_state === 'REPORTED',
  }
}

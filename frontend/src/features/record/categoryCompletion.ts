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

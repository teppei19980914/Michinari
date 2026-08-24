import type { SubjectRead } from '../../api/goals'

/**
 * 期間開始日が本日より過去かどうかを判定する（仕様書6.2「受験日が期間の場合、期間開始日が
 * 本日より過去である場合に警告を表示する」）。ISO 8601形式（YYYY-MM-DD）の文字列比較のため、
 * クライアント側でDateオブジェクトを生成しない（CLAUDE.md「クライアント側での論理日の判断」
 * 禁止 — todayLogicalDateはサーバのGET /records/todayから取得した値を渡すこと）。
 */
export function isSubjectRangeStartInPast(
  subject: Pick<SubjectRead, 'exam_date_type' | 'exam_date_from'>,
  todayLogicalDate: string | undefined,
): boolean {
  if (subject.exam_date_type !== 'RANGE' || !subject.exam_date_from || !todayLogicalDate) {
    return false
  }
  return subject.exam_date_from < todayLogicalDate
}

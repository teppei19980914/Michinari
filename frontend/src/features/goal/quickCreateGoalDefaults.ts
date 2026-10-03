/** 読書・仕事の簡易作成フォーム（仕様書「読書・仕事モードの簡易作成」）で、
 * 利用者に入力させない必須項目へ既定値を補う判定ロジック。
 *
 * 読書のAPI（BookCreate）は総ページ数・読了目標日を必須とし、仕事のAPI
 * （WorkAssignmentCreate）は想定業務内容を必須とするが、簡易フォームはこれらを
 * 任意または未入力のまま作成できることを完了条件としている。未入力時は暫定値を
 * 補い、後から目標詳細画面（BookTab/WorkAssignmentTab）で訂正できる前提とする
 * （総ページ数の暫定値1は、データ構造編1.1改20の欠損データ補填と同じ考え方）。 */

/** 読書の総ページ数。未入力なら暫定値1を補う。 */
export function resolveQuickBookTotalPages(totalPagesInput: string): number {
  return totalPagesInput.trim() === '' ? 1 : Number(totalPagesInput)
}

/** 読了目標日。読書開始日からの日数（既定90日）を加えた暫定値とする。
 *
 * UTC基準で組み立てる（`features/goal/materialDueDate.ts`の`isoDateMinusOneDay`と同じ方式）。
 * `new Date(dateString)`を実行環境のローカルタイムゾーンのまま`setDate`/`toISOString`に
 * 混ぜて使うと、UTCから見て正のタイムゾーン（日本時間など）で日付が1日ずれる
 * （ローカル日付とUTC出力の取り違え）。 */
export function resolveQuickBookDueDate(startDate: string, days = 90): string {
  const [year, month, day] = startDate.split('-').map(Number)
  const due = new Date(Date.UTC(year, month - 1, day))
  due.setUTCDate(due.getUTCDate() + days)
  return due.toISOString().slice(0, 10)
}

/** 仕事の想定業務内容。未入力なら案件名（目標名）をそのまま補う。 */
export function resolveQuickWorkExpectedContent(summaryInput: string, goalName: string): string {
  return summaryInput.trim() === '' ? goalName : summaryInput
}

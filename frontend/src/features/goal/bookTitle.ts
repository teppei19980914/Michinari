/**
 * 書籍タブの書名初期値を決定する。既存の書籍レコードがあればその書名を、
 * まだ書籍未登録（新規作成前）であれば目標設定画面で入力した目標名（書名）を
 * 転記する。ユーザーが目標設定画面と書籍タブで同じ書名を二重入力させられる
 * 問題への対応（目標名は登録済み書籍のtitleと連動しないため、フォーム初期値
 * としてのみ転記し、以降はユーザーの編集を優先する）。
 *
 * @param bookTitle 登録済み書籍のtitle（未登録ならundefined）
 * @param goalName 目標名（GoalDetailRead.name）
 * @returns フォームに表示する初期書名
 */
export function resolveInitialBookTitle(
  bookTitle: string | undefined,
  goalName: string,
): string {
  return bookTitle ?? goalName
}

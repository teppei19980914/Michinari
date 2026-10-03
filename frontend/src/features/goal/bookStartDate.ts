/** 書籍タブの読書開始日初期値を決定する。書名の転記（bookTitle.ts）と同じ考え方で、
 * まだ書籍未登録（新規作成前）であれば基本情報タブで入力した目標開始日を転記する。
 * ユーザーが基本情報タブと書籍タブで同じ開始日を二重入力させられる問題への対応
 * （目標開始日は登録済み書籍のstart_dateとは連動しないため、フォーム初期値としてのみ
 * 転記し、以降はユーザーの編集を優先する）。
 *
 * @param bookStartDate 登録済み書籍のstart_date（未登録ならundefined）
 * @param goalStartDate 目標の開始日（GoalDetailRead.start_date）
 * @returns フォームに表示する初期読書開始日
 */
export function resolveInitialBookStartDate(
  bookStartDate: string | undefined,
  goalStartDate: string,
): string {
  return bookStartDate ?? goalStartDate
}

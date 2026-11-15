/** 出題セッションの進行（現在位置の判定・前進）の純粋関数。復習クイズ・単語帳の問題集の
 * 両方が同じ「連番の問題を1問ずつ進める」構造を持つため共通化する（CODING_RULES.md
 * ①DRYの原則、dry-reviewerレビューで検出、2026-11-15）。 */
export function isLastQuestion(currentIndex: number, totalCount: number): boolean {
  return currentIndex >= totalCount - 1
}

export function nextIndex(currentIndex: number): number {
  return currentIndex + 1
}

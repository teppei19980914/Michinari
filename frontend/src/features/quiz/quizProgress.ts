/** 復習クイズの進行状況の純粋関数（テスト容易性のためJSXから分離、CODING_RULES.md）。 */
export function isLastQuestion(currentIndex: number, totalCount: number): boolean {
  return currentIndex >= totalCount - 1
}

export function nextIndex(currentIndex: number): number {
  return currentIndex + 1
}

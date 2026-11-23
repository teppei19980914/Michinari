/**
 * 行・列の並べ替え（上下・左右のボタン、D-13）。ドラッグ操作は対象外。
 * `vocabDeckOrder.ts`と同型の純粋関数（CODING_RULES.md DRYの原則）。行（上下）・追加列
 * （左右）の両方から使える汎用実装にする。
 */
export function moveByOffset<T>(items: T[], index: number, offset: number): T[] {
  const target = index + offset
  if (target < 0 || target >= items.length) {
    return items
  }
  const next = [...items]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

export function insertBelow<T>(items: T[], index: number, newItem: T): T[] {
  const next = [...items]
  next.splice(index + 1, 0, newItem)
  return next
}

export function removeAt<T>(items: T[], index: number): T[] {
  return items.filter((_, i) => i !== index)
}

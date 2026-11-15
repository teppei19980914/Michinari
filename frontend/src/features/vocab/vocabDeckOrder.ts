/** デッキの並び替え（上下移動）の純粋関数（CODING_RULES.md「フロントの分岐は.tsへ切り出す」）。 */
export function swapByOffset(deckIds: number[], index: number, offset: number): number[] {
  const target = index + offset
  if (target < 0 || target >= deckIds.length) {
    return deckIds
  }
  const next = [...deckIds]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

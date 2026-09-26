import type { CompletedReadingBook } from '../../api/goals'

export type GroupedCompletedBooks = {
  onShelf: { completed: CompletedReadingBook[]; interrupted: CompletedReadingBook[] }
  archived: { completed: CompletedReadingBook[]; interrupted: CompletedReadingBook[] }
}

/** 直近にクローズした本を先頭にする（closed_atが同着の場合はidを補助キーにする。CODING_RULES.md）。 */
function byClosedAtDesc(a: CompletedReadingBook, b: CompletedReadingBook): number {
  const closedAtDiff = (b.goal.closed_at ?? '').localeCompare(a.goal.closed_at ?? '')
  return closedAtDiff !== 0 ? closedAtDiff : b.goal.id - a.goal.id
}

/**
 * 本棚（SC-18）の表示区分に振り分ける。呼び出し側（listCompletedReadingBooks）が既に
 * category=READING かつ status が CLOSED_WITH_RESULT/CLOSED_WITHOUT_RESULT のいずれかに
 * 絞り込んだ結果を渡す前提。
 *
 * - 読了/中断の区分: goal.status
 * - 棚上/しまった本の区分: goal.archived_at（設計時の確定事項「アーカイブする＝棚からしまう」、
 *   本棚専用の状態列は追加しない）
 */
export function groupCompletedBooks(entries: CompletedReadingBook[]): GroupedCompletedBooks {
  const result: GroupedCompletedBooks = {
    onShelf: { completed: [], interrupted: [] },
    archived: { completed: [], interrupted: [] },
  }
  for (const entry of entries) {
    const bucket = entry.goal.archived_at === null ? result.onShelf : result.archived
    const key = entry.goal.status === 'CLOSED_WITH_RESULT' ? 'completed' : 'interrupted'
    bucket[key].push(entry)
  }
  result.onShelf.completed.sort(byClosedAtDesc)
  result.onShelf.interrupted.sort(byClosedAtDesc)
  result.archived.completed.sort(byClosedAtDesc)
  result.archived.interrupted.sort(byClosedAtDesc)
  return result
}

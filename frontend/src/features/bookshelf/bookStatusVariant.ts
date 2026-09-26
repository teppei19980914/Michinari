import type { GoalRead } from '../../api/goals'

export type BookSpineVariant = 'completed' | 'interrupted'

type GoalStatus = GoalRead['status']

/** goal.statusから本棚の表示区分を決める（CLOSED_WITH_RESULT=読了、CLOSED_WITHOUT_RESULT=中断）。
 * listCompletedReadingBooksが既にこの2状態のみへ絞り込んでいる前提。 */
export function resolveBookSpineVariant(status: GoalStatus): BookSpineVariant {
  return status === 'CLOSED_WITH_RESULT' ? 'completed' : 'interrupted'
}

/** 読了/中断で背表紙の見た目を分ける（2026-09-26 ユーザー要望で木製本棚を模した縦書き背表紙
 * デザインへ変更。以前は「写実的な本棚グラフィックは使わない」方針だったが、この変更で上書き
 * 確定）。中断本は彩度を落とし「読みかけで棚に戻した」印象にする。
 * BookSpineCard（本棚一覧）で使う。BookInfoTab（書籍詳細）はBOOK_STATUS_BADGE_CLASSのみ使う。 */
export const BOOK_SPINE_ACCENT_CLASS: Record<BookSpineVariant, string> = {
  completed: 'text-white',
  interrupted: 'text-white grayscale opacity-70',
}

export const BOOK_STATUS_BADGE_CLASS: Record<BookSpineVariant, string> = {
  completed: 'bg-emerald-100 text-emerald-800',
  interrupted: 'bg-gray-100 text-gray-600',
}

const SPINE_HUE_CLASSES = [
  'bg-amber-700',
  'bg-rose-800',
  'bg-sky-800',
  'bg-emerald-800',
  'bg-indigo-800',
  'bg-teal-800',
  'bg-orange-800',
  'bg-stone-700',
] as const

/** 実際の本棚のように背表紙の色にばらつきを出す。goal.idから決定的に選ぶため、同じ本は
 * 再描画しても常に同じ色になる。 */
export function resolveSpineHueClass(goalId: number): string {
  return SPINE_HUE_CLASSES[goalId % SPINE_HUE_CLASSES.length]
}

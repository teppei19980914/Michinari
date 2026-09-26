import type { GoalRead } from '../../api/goals'

export type BookSpineVariant = 'completed' | 'interrupted'

type GoalStatus = GoalRead['status']

/** goal.statusから本棚の表示区分を決める（CLOSED_WITH_RESULT=読了、CLOSED_WITHOUT_RESULT=中断）。
 * listCompletedReadingBooksが既にこの2状態のみへ絞り込んでいる前提。 */
export function resolveBookSpineVariant(status: GoalStatus): BookSpineVariant {
  return status === 'CLOSED_WITH_RESULT' ? 'completed' : 'interrupted'
}

/** 読了/中断で背表紙・バッジの見た目を分ける（設計協議で確定。写実的な本棚グラフィックは使わず、
 * 既存のTailwindフラットデザインに合わせて縁取りとバッジの色だけで区別する）。
 * BookSpineCard（本棚一覧）とBookInfoTab（書籍詳細）の両方で使うため共有する。 */
export const BOOK_SPINE_ACCENT_CLASS: Record<BookSpineVariant, string> = {
  completed: 'border-l-4 border-emerald-500',
  interrupted: 'border-l-4 border-gray-300 opacity-80',
}

export const BOOK_STATUS_BADGE_CLASS: Record<BookSpineVariant, string> = {
  completed: 'bg-emerald-100 text-emerald-800',
  interrupted: 'bg-gray-100 text-gray-600',
}

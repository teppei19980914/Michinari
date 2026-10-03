import { t } from '../../locales/t'
import type { CompletedReadingBook, GoalRead } from '../../api/goals'
import { BookSpineCard } from './BookSpineCard'
import type { BookSpineVariant } from './bookStatusVariant'

/** 本棚（SC-18）の1セクション（読了棚/中断棚/しまった本）。1関数100行の上限
 * （CODING_RULES.md「保守性（複雑度）」）への対応でBookshelfPage.tsxから切り出した。
 * 3セクションとも同じ構造（見出し＋木製の棚板＋背表紙の一覧）のため共通化する（DRYの原則）。
 * 木目調の棚板に背表紙を並べる（2026-09-26、ユーザー要望でフラットな一覧から変更）。
 * 同一セクション内はcanArchiveGoalの判定結果が揃う（entries全件が同じgoal.status系統のため）
 * ので、背表紙の高さは全件同じになりitems-endで棚板にきれいに揃う。 */
export function BookShelfSection({
  titleKey,
  entries,
  resolveVariant,
  onArchive,
  onUnarchive,
  onRequestDelete,
}: {
  titleKey: string
  entries: CompletedReadingBook[]
  resolveVariant: (entry: CompletedReadingBook) => BookSpineVariant
  onArchive: (goalId: number) => void
  onUnarchive: (goalId: number) => void
  onRequestDelete: (goal: GoalRead) => void
}) {
  if (entries.length === 0) {
    return null
  }

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-gray-700">{t(titleKey)}</h2>
      <div className="rounded-lg border border-amber-900/40 bg-gradient-to-b from-amber-100/70 to-amber-200/70 p-3 shadow-inner">
        <ul className="flex items-end gap-2 overflow-x-auto pb-3">
          {entries.map((entry) => (
            <li key={entry.goal.id} className="shrink-0">
              <BookSpineCard
                entry={entry}
                variant={resolveVariant(entry)}
                onArchive={onArchive}
                onUnarchive={onUnarchive}
                onRequestDelete={onRequestDelete}
              />
            </li>
          ))}
        </ul>
        <div className="h-3 rounded-b-md bg-gradient-to-b from-amber-800 to-amber-950 shadow-md" />
      </div>
    </section>
  )
}

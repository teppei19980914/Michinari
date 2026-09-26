import { t } from '../../locales/t'
import type { CompletedReadingBook, GoalRead } from '../../api/goals'
import { BookSpineCard } from './BookSpineCard'
import type { BookSpineVariant } from './bookStatusVariant'

/** 本棚（SC-18）の1セクション（読了棚/中断棚/しまった本）。1関数100行の上限
 * （CODING_RULES.md「保守性（複雑度）」）への対応でBookshelfPage.tsxから切り出した。
 * 3セクションとも同じ構造（見出し＋カード一覧）のため共通化する（DRYの原則）。 */
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
      <ul className="flex flex-col gap-2">
        {entries.map((entry) => (
          <li key={entry.goal.id}>
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
    </section>
  )
}

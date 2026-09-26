import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Card } from '../../components/Card'
import { Button } from '../../components/Button'
import type { CompletedReadingBook, GoalRead } from '../../api/goals'
import { canArchiveGoal } from '../goal/goalStatus'
import { BOOK_SPINE_ACCENT_CLASS, BOOK_STATUS_BADGE_CLASS, type BookSpineVariant } from './bookStatusVariant'

/** 本棚（SC-18）の書籍1冊分のカード。GoalsListPageのGoalCardと同じ操作パターン
 * （アーカイブ確認ダイアログ・復元・完全削除）を踏襲する。 */
export function BookSpineCard({
  entry,
  variant,
  onArchive,
  onUnarchive,
  onRequestDelete,
}: {
  entry: CompletedReadingBook
  variant: BookSpineVariant
  onArchive: (goalId: number) => void
  onUnarchive: (goalId: number) => void
  onRequestDelete: (goal: GoalRead) => void
}) {
  const { goal, book } = entry
  const isArchived = goal.archived_at !== null

  return (
    <Card
      className={`flex items-center justify-between gap-3 hover:border-emerald-300 ${BOOK_SPINE_ACCENT_CLASS[variant]}`}
    >
      <Link to={ROUTES.bookDetail(goal.id)} className="flex flex-1 flex-col gap-1">
        <span className="font-medium text-gray-900">{book.title}</span>
        <span className="flex items-center gap-2 text-xs text-gray-500">
          {book.author && <span>{book.author}</span>}
          <span className={`rounded-full px-2 py-0.5 font-medium ${BOOK_STATUS_BADGE_CLASS[variant]}`}>
            {t(`bookshelf.book.status.${variant}`)}
          </span>
        </span>
      </Link>
      {!isArchived && canArchiveGoal(goal.status, goal.archived_at) && (
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            if (window.confirm(t('bookshelf.book.archiveConfirm'))) {
              onArchive(goal.id)
            }
          }}
        >
          {t('bookshelf.book.archiveButton')}
        </Button>
      )}
      {isArchived && (
        <>
          <Button type="button" variant="secondary" onClick={() => onUnarchive(goal.id)}>
            {t('bookshelf.book.restoreButton')}
          </Button>
          <Button type="button" variant="secondary" onClick={() => onRequestDelete(goal)}>
            {t('bookshelf.book.deleteCompletelyButton')}
          </Button>
        </>
      )}
    </Card>
  )
}

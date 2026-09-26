import { Link } from 'react-router-dom'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Button } from '../../components/Button'
import type { CompletedReadingBook, GoalRead } from '../../api/goals'
import { canArchiveGoal } from '../goal/goalStatus'
import {
  BOOK_SPINE_ACCENT_CLASS,
  BOOK_STATUS_BADGE_CLASS,
  resolveSpineHueClass,
  type BookSpineVariant,
} from './bookStatusVariant'

/** 本棚（SC-18）の書籍1冊分。縦書きの背表紙（2026-09-26 ユーザー要望で確定）＋操作ボタンの構成。
 * 背表紙の縦横サイズはclamp()でビューポート幅に連動させ、ウィンドウリサイズに追従して
 * 連続的に拡大縮小する（ブレークポイント単位の段階変化ではなく動的リサイズにする要望のため）。
 * 操作パターン（アーカイブ確認ダイアログ・復元・完全削除）はGoalsListPageのGoalCardと同じ。 */
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
    <div className="flex w-[clamp(3rem,7vw,5.5rem)] flex-col items-stretch gap-1.5">
      <Link
        to={ROUTES.bookDetail(goal.id)}
        title={book.author ? `${book.title} / ${book.author}` : book.title}
        className={`flex h-[clamp(8rem,20vw,14rem)] w-full flex-col items-center justify-center gap-1.5 overflow-hidden rounded-sm border-x border-t border-black/20 px-1 py-2 shadow-md transition-transform hover:-translate-y-1 ${resolveSpineHueClass(goal.id)} ${BOOK_SPINE_ACCENT_CLASS[variant]}`}
      >
        <span
          className={`shrink-0 rounded-full px-1.5 py-0.5 text-[clamp(0.5rem,0.9vw,0.65rem)] font-medium leading-none ${BOOK_STATUS_BADGE_CLASS[variant]}`}
        >
          {t(`bookshelf.book.status.${variant}`)}
        </span>
        <span className="text-[clamp(0.75rem,1.6vw,0.95rem)] font-semibold [writing-mode:vertical-rl]">
          {book.title}
        </span>
        {book.author && (
          <span className="text-[clamp(0.55rem,1vw,0.7rem)] opacity-80 [writing-mode:vertical-rl]">
            {book.author}
          </span>
        )}
      </Link>

      {canArchiveGoal(goal.status, goal.archived_at) && (
        <Button
          type="button"
          variant="secondary"
          className="!px-1.5 !py-1 !text-xs"
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
          <Button
            type="button"
            variant="secondary"
            className="!px-1.5 !py-1 !text-xs"
            onClick={() => onUnarchive(goal.id)}
          >
            {t('bookshelf.book.restoreButton')}
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="!px-1.5 !py-1 !text-xs"
            onClick={() => onRequestDelete(goal)}
          >
            {t('bookshelf.book.deleteCompletelyButton')}
          </Button>
        </>
      )}
    </div>
  )
}

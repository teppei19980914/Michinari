import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { BookRead, GoalRead } from '../../api/goals'
import { BOOK_STATUS_BADGE_CLASS, resolveBookSpineVariant } from './bookStatusVariant'

/** 本棚の書籍詳細（SC-19）「書誌情報」タブ。is_achievedバッジは出さない
 * （読了棚に置かれていること自体が達成の表現であり冗長になるため、設計協議で確定）。 */
export function BookInfoTab({ book, goal }: { book: BookRead; goal: GoalRead }) {
  const variant = resolveBookSpineVariant(goal.status)
  const endDate = goal.closed_at?.slice(0, 10) ?? book.due_date

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold text-gray-900">{book.title}</h2>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${BOOK_STATUS_BADGE_CLASS[variant]}`}
        >
          {t(`bookshelf.book.status.${variant}`)}
        </span>
      </div>
      {book.author && <p className="text-sm text-gray-500">{book.author}</p>}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-gray-500">{t('bookshelf.detail.info.period')}</dt>
        <dd className="text-gray-900">
          {book.start_date} 〜 {endDate}
        </dd>
        <dt className="text-gray-500">{t('bookshelf.detail.info.totalPages')}</dt>
        <dd className="text-gray-900">{book.total_pages}</dd>
        {book.progress_rate !== null && (
          <>
            <dt className="text-gray-500">{t('bookshelf.detail.info.progressRate')}</dt>
            <dd className="text-gray-900">{Math.round(book.progress_rate * 100)}%</dd>
          </>
        )}
      </dl>

      {variant === 'interrupted' && (
        <p className="text-sm text-gray-500">{t('bookshelf.detail.info.interruptedNote')}</p>
      )}
    </Card>
  )
}

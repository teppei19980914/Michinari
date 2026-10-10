import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { useToast } from '../components/toastContext'
import { archiveGoal, listCompletedReadingBooks, unarchiveGoal, type GoalRead } from '../api/goals'
import { groupCompletedBooks } from '../features/bookshelf/groupCompletedBooks'
import { BookShelfSection } from '../features/bookshelf/BookShelfSection'
import { resolveBookSpineVariant } from '../features/bookshelf/bookStatusVariant'
import { DeleteGoalModal } from '../features/goal/DeleteGoalModal'
import { QUERY_KEYS } from '../constants/queryKeys'

/** SC-18 本棚。読了・中断した読書目標を書籍カードとして表示する（GoalsListPageのクローズ済み
 * 行を置き換えるものではなく、読書という体験に合わせた追加の入口。設計協議で確定）。
 *
 * 「アーカイブする」＝棚からしまう、という対応にし、本棚専用の状態列は追加しない
 * （既存の goal.archived_at をそのまま使う）。アーカイブ/復元/完全削除の配線は
 * GoalsListPage.tsx の GoalCard と同型だが、既存ファイルへの影響を避けるためこちらに
 * 直接実装する（デグレ回避を優先。共通化するほどの規模ではない）。 */
export function BookshelfPage() {
  const [showArchived, setShowArchived] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<GoalRead | null>(null)
  const queryClient = useQueryClient()
  const { showApiErrorWithTitle } = useToast()

  const booksQuery = useQuery({
    queryKey: QUERY_KEYS.completedReadingBooks(),
    queryFn: listCompletedReadingBooks,
  })

  const archiveMutation = useMutation({
    mutationFn: archiveGoal,
    meta: { overlay: 'deleting' },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.completedReadingBooks() }),
    onError: (error) => showApiErrorWithTitle(t('bookshelf.book.archiveButton'), error),
  })
  const unarchiveMutation = useMutation({
    mutationFn: unarchiveGoal,
    meta: { overlay: 'saving' },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.completedReadingBooks() }),
    onError: (error) => showApiErrorWithTitle(t('bookshelf.book.restoreButton'), error),
  })

  const grouped = groupCompletedBooks(booksQuery.data ?? [])
  const hasAnyOnShelf = grouped.onShelf.completed.length > 0 || grouped.onShelf.interrupted.length > 0
  const hasAnyArchived = grouped.archived.completed.length > 0 || grouped.archived.interrupted.length > 0
  const archivedEntries = [...grouped.archived.completed, ...grouped.archived.interrupted]

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-text-primary">{t('bookshelf.title')}</h1>

      {booksQuery.isLoading && <p className="text-sm text-text-faint">{t('common.loading')}</p>}

      {booksQuery.data && !hasAnyOnShelf && !hasAnyArchived && (
        <p className="text-sm text-text-faint">{t('bookshelf.empty')}</p>
      )}

      <BookShelfSection
        titleKey="bookshelf.shelf.completedTitle"
        entries={grouped.onShelf.completed}
        resolveVariant={() => 'completed'}
        onArchive={archiveMutation.mutate}
        onUnarchive={unarchiveMutation.mutate}
        onRequestDelete={setDeleteTarget}
      />

      <BookShelfSection
        titleKey="bookshelf.shelf.interruptedTitle"
        entries={grouped.onShelf.interrupted}
        resolveVariant={() => 'interrupted'}
        onArchive={archiveMutation.mutate}
        onUnarchive={unarchiveMutation.mutate}
        onRequestDelete={setDeleteTarget}
      />

      {hasAnyArchived && (
        <label className="flex items-center gap-2 text-sm text-text-muted">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
          />
          {t('bookshelf.showArchivedToggle')}
        </label>
      )}

      {showArchived && (
        <BookShelfSection
          titleKey="bookshelf.archivedSectionTitle"
          entries={archivedEntries}
          resolveVariant={(entry) => resolveBookSpineVariant(entry.goal.status)}
          onArchive={archiveMutation.mutate}
          onUnarchive={unarchiveMutation.mutate}
          onRequestDelete={setDeleteTarget}
        />
      )}

      <DeleteGoalModal
        goal={deleteTarget}
        onClose={() => {
          setDeleteTarget(null)
          // DeleteGoalModalの削除成功時の無効化対象はQUERY_KEYS.goals()のみ（目標一覧向け）。
          // 本棚は別キー（completedReadingBooks）で取得しているため、モーダルを閉じるたびに
          // こちらも無効化する（キャンセル時の無駄な再取得は許容する）。
          queryClient.invalidateQueries({ queryKey: QUERY_KEYS.completedReadingBooks() })
        }}
      />
    </div>
  )
}

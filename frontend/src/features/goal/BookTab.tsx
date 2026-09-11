import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { ROUTES } from '../../constants/routes'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import {
  completeBook,
  createBook,
  updateBook,
  type BookRead,
  type GoalDetailRead,
} from '../../api/goals'
import { generateRetrospective } from '../../api/closure'
import { resolveInitialBookTitle } from './bookTitle'

function BookForm({
  goalId,
  goalName,
  book,
  onDone,
}: {
  goalId: number
  goalName: string
  book?: BookRead
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [title, setTitle] = useState(resolveInitialBookTitle(book?.title, goalName))
  const [author, setAuthor] = useState(book?.author ?? '')
  const [totalPages, setTotalPages] = useState(
    book?.total_pages === undefined ? '' : String(book.total_pages),
  )
  const [startDate, setStartDate] = useState(book?.start_date ?? '')
  const [dueDate, setDueDate] = useState(book?.due_date ?? '')

  const payload = {
    title,
    author: author === '' ? null : author,
    total_pages: Number(totalPages),
    start_date: startDate,
    due_date: dueDate,
  }

  const mutation = useMutation({
    mutationFn: () => (book ? updateBook(book.id, payload) : createBook(goalId, payload)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goalId] })
      onDone()
    },
    onError: showApiError,
  })

  return (
    <Card>
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.book.titleLabel')}
          <Input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.book.authorLabel')}
          <Input value={author} onChange={(e) => setAuthor(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.book.totalPagesLabel')}
          <Input
            type="number"
            min={1}
            value={totalPages}
            onChange={(e) => setTotalPages(e.target.value)}
            required
          />
        </label>
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.book.startDateLabel')}
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.book.dueDateLabel')}
            <Input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              required
            />
          </label>
        </div>
        <div className="flex justify-end gap-2">
          {book && (
            <Button type="button" variant="secondary" onClick={onDone}>
              {t('common.action.cancel')}
            </Button>
          )}
          <Button type="submit" disabled={mutation.isPending}>
            {t('common.action.save')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

function CompleteBookModal({
  bookId,
  open,
  onClose,
  onCompleted,
}: {
  bookId: number
  open: boolean
  onClose: () => void
  onCompleted: () => void
}) {
  const { showApiError } = useToast()

  const mutation = useMutation({
    mutationFn: () => completeBook(bookId),
    onSuccess: onCompleted,
    onError: showApiError,
  })

  return (
    <Modal open={open} onClose={onClose} title={t('goals.book.completeConfirm.title')}>
      <p className="text-sm text-gray-700">{t('goals.book.completeConfirm.body')}</p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          {t('common.action.cancel')}
        </Button>
        <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
          {t('common.action.confirm')}
        </Button>
      </div>
    </Modal>
  )
}

function BookProgress({ book }: { book: BookRead }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-600">
      <dt className="text-gray-400">{t('goals.book.remainingDaysLabel')}</dt>
      <dd>{t('goals.book.remainingDaysValue', { days: book.remaining_days })}</dd>
      <dt className="text-gray-400">{t('goals.book.lastReadingDateLabel')}</dt>
      <dd>{book.last_reading_date ?? t('goals.book.lastReadingDateUnavailable')}</dd>
      <dt className="text-gray-400">{t('goals.book.currentStreakLabel')}</dt>
      <dd>{t('goals.book.currentStreakValue', { days: book.current_streak })}</dd>
      {book.progress_rate !== null && (
        <>
          <dt className="text-gray-400">{t('goals.book.progressLabel')}</dt>
          <dd>
            {book.current_page} / {book.total_pages}（{Math.round(book.progress_rate * 100)}%）
          </dd>
        </>
      )}
    </dl>
  )
}

/** 書籍タブ（読書目標。仕様書6.2「読書目標（category=READINGの場合）」）。
 * 資格試験の試験科目・教材タブに相当する読書版で、1目標1冊のため単一のカードで
 * 登録・編集・進捗表示・読了操作を行う。 */
export function BookTab({ goal, readOnly }: { goal: GoalDetailRead; readOnly: boolean }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [completeModalOpen, setCompleteModalOpen] = useState(false)

  if (!goal.book) {
    if (readOnly) {
      return <p className="text-sm text-gray-500">{t('goals.book.empty')}</p>
    }
    return <BookForm goalId={goal.id} goalName={goal.name} onDone={() => undefined} />
  }

  const book = goal.book

  if (editing) {
    return <BookForm goalId={goal.id} goalName={goal.name} book={book} onDone={() => setEditing(false)} />
  }

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col gap-3">
        <div>
          <p className="font-medium text-gray-900">{book.title}</p>
          {book.author && <p className="text-sm text-gray-500">{book.author}</p>}
        </div>
        <BookProgress book={book} />
        {!readOnly && (
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}>
              {t('common.action.edit')}
            </Button>
            {goal.status === 'ACTIVE' && (
              <Button onClick={() => setCompleteModalOpen(true)}>
                {t('goals.book.completeButton')}
              </Button>
            )}
          </div>
        )}
      </Card>

      <CompleteBookModal
        bookId={book.id}
        open={completeModalOpen}
        onClose={() => setCompleteModalOpen(false)}
        onCompleted={() => {
          // 読了レポートの生成はクローズ処理の成否に影響させない（ExamResultPageのCloseGoalModal
          // と同じ方針。仕様書6.9・実装フェーズ分割計画書Phase10注意点）。失敗時もエクスポート
          // 画面へは遷移し、同画面の生成ボタンから再試行できる。
          generateRetrospective(goal.id, false).catch(() => undefined)
          queryClient.invalidateQueries({ queryKey: ['goal', goal.id] })
          setCompleteModalOpen(false)
          navigate(ROUTES.goalExport(goal.id))
        }}
      />
    </div>
  )
}

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Modal } from '../../components/Modal'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { activateGoal, createBook, createGoal, createWorkAssignment } from '../../api/goals'
import { getToday } from '../../api/records'
import { QUERY_KEYS } from '../../constants/queryKeys'
import {
  resolveQuickBookDueDate,
  resolveQuickBookTotalPages,
  resolveQuickWorkExpectedContent,
} from './quickCreateGoalDefaults'

type QuickCreateCategory = 'READING' | 'WORK'

/** カテゴリに応じて入力欄を出し分ける（読書＝著者・総ページ数、仕事＝概要）。
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）に収めるため、
 * QuickCreateGoalModal本体から入力欄の並びだけを切り出したもの。 */
function QuickCreateFields({
  category,
  name,
  onChangeName,
  author,
  onChangeAuthor,
  totalPagesInput,
  onChangeTotalPagesInput,
  summary,
  onChangeSummary,
}: {
  category: QuickCreateCategory
  name: string
  onChangeName: (value: string) => void
  author: string
  onChangeAuthor: (value: string) => void
  totalPagesInput: string
  onChangeTotalPagesInput: (value: string) => void
  summary: string
  onChangeSummary: (value: string) => void
}) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {category === 'READING'
          ? t('goals.new.quickCreate.reading.titleLabel')
          : t('goals.new.quickCreate.work.nameLabel')}
        <Input value={name} onChange={(e) => onChangeName(e.target.value)} required />
      </label>

      {category === 'READING' ? (
        <>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t('goals.new.quickCreate.reading.authorLabel')}
            <Input value={author} onChange={(e) => onChangeAuthor(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t('goals.new.quickCreate.reading.totalPagesLabel')}
            <Input
              type="number"
              min={1}
              value={totalPagesInput}
              onChange={(e) => onChangeTotalPagesInput(e.target.value)}
            />
          </label>
        </>
      ) : (
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.new.quickCreate.work.summaryLabel')}
          <Input value={summary} onChange={(e) => onChangeSummary(e.target.value)} />
        </label>
      )}
    </>
  )
}

/** 読書・仕事の簡易作成（仕様書「読書・仕事モードの簡易作成」）。
 *
 * 資格試験と異なりウィザードを介さず1画面で完結させる。目標本体の作成・書籍/案件情報の
 * 登録・進行中への遷移をまとめて行う（呼び出し元は完了後の画面遷移のみを担う）。
 * 開始日は利用者に入力させず論理的な本日を使う（CLAUDE.md「クライアント側での論理日の
 * 判断」禁止のため `GET /records/today` から取得する）。 */
export function QuickCreateGoalModal({
  open,
  category,
  onClose,
  onCreated,
}: {
  open: boolean
  category: QuickCreateCategory
  onClose: () => void
  onCreated: (goalId: number) => void
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const [name, setName] = useState('')
  const [author, setAuthor] = useState('')
  const [totalPagesInput, setTotalPagesInput] = useState('')
  const [summary, setSummary] = useState('')

  const todayQuery = useQuery({ queryKey: QUERY_KEYS.today(), queryFn: getToday, enabled: open })

  const mutation = useMutation({
    mutationFn: async () => {
      const startDate = todayQuery.data?.logical_date
      /* v8 ignore next 3 -- 送信ボタンは todayQuery.data が無い間disabledのため到達しない
         （防御的なガード）。 */
      if (!startDate) {
        throw new Error('logical_date is not loaded yet')
      }
      const goal = await createGoal({ category, name, start_date: startDate })
      if (category === 'READING') {
        await createBook(goal.id, {
          title: name,
          author: author === '' ? null : author,
          total_pages: resolveQuickBookTotalPages(totalPagesInput),
          start_date: startDate,
          due_date: resolveQuickBookDueDate(startDate),
        })
      } else {
        await createWorkAssignment(goal.id, {
          client_name: null,
          expected_content: resolveQuickWorkExpectedContent(summary, name),
          start_date: startDate,
        })
      }
      await activateGoal(goal.id)
      return goal
    },
    onSuccess: (goal) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goals() })
      setName('')
      setAuthor('')
      setTotalPagesInput('')
      setSummary('')
      onClose()
      onCreated(goal.id)
    },
    onError: showApiError,
  })

  const title =
    category === 'READING' ? t('goals.new.quickCreate.reading.title') : t('goals.new.quickCreate.work.title')

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <QuickCreateFields
          category={category}
          name={name}
          onChangeName={setName}
          author={author}
          onChangeAuthor={setAuthor}
          totalPagesInput={totalPagesInput}
          onChangeTotalPagesInput={setTotalPagesInput}
          summary={summary}
          onChangeSummary={setSummary}
        />

        <div className="mt-2 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('common.action.cancel')}
          </Button>
          <Button type="submit" disabled={mutation.isPending || !todayQuery.data}>
            {t('goals.new.quickCreate.submitButton')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

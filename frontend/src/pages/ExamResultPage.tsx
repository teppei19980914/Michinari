import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { Textarea } from '../components/Textarea'
import { useToast } from '../components/Toast'
import { apiErrorMessage } from '../api/client'
import { getGoal, type SubjectRead } from '../api/goals'
import { generateRetrospective, registerExamResult, updateExamResult } from '../api/closure'
import { CloseGoalModal } from '../features/goal/CloseGoalModal'
import { isClosedGoalStatus } from '../features/goal/goalStatus'

const RESULT_TYPES = ['PASS', 'FAIL', 'PENDING'] as const

function ExamResultForm({ goalId, subject }: { goalId: number; subject: SubjectRead }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const existing = subject.exam_result
  const [editing, setEditing] = useState(existing === null)
  const [takenDate, setTakenDate] = useState(existing?.taken_date ?? '')
  const [result, setResult] = useState<(typeof RESULT_TYPES)[number]>(
    existing?.result ?? 'PENDING',
  )
  const [score, setScore] = useState(
    existing?.score === null || existing?.score === undefined ? '' : String(existing.score),
  )
  const [evaluation, setEvaluation] = useState(existing?.evaluation ?? '')
  const [note, setNote] = useState(existing?.note ?? '')

  const payload = {
    taken_date: takenDate,
    result,
    score: score === '' ? null : Number(score),
    evaluation: evaluation === '' ? null : evaluation,
    note: note === '' ? null : note,
  }

  const mutation = useMutation({
    mutationFn: () =>
      existing
        ? updateExamResult(existing.id, payload)
        : registerExamResult(subject.id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goal', goalId] })
      setEditing(false)
    },
    onError: showApiError,
  })

  if (!editing && existing) {
    return (
      <Card className="flex items-center justify-between">
        <div>
          <p className="font-medium text-gray-900">{subject.name}</p>
          <p className="text-sm text-gray-500">
            {t('goalResult.registeredBadge')}: {t(`goalResult.result.${existing.result}`)}
            {existing.score !== null && ` (${existing.score})`}
          </p>
        </div>
        <Button variant="secondary" onClick={() => setEditing(true)}>
          {t('goalResult.editButton')}
        </Button>
      </Card>
    )
  }

  return (
    <Card>
      <p className="mb-3 font-medium text-gray-900">{subject.name}</p>
      <form
        className="flex flex-col gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          mutation.mutate()
        }}
      >
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goalResult.takenDateLabel')}
          <Input
            type="date"
            value={takenDate}
            onChange={(e) => setTakenDate(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goalResult.resultLabel')}
          <select
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            value={result}
            onChange={(e) => setResult(e.target.value as (typeof RESULT_TYPES)[number])}
          >
            {RESULT_TYPES.map((value) => (
              <option key={value} value={value}>
                {t(`goalResult.result.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goalResult.scoreLabel')}
          <Input type="number" value={score} onChange={(e) => setScore(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goalResult.evaluationLabel')}
          <Input value={evaluation} onChange={(e) => setEvaluation(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goalResult.noteLabel')}
          <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <div className="flex justify-end gap-2">
          {existing && (
            <Button type="button" variant="secondary" onClick={() => setEditing(false)}>
              {t('common.action.cancel')}
            </Button>
          )}
          <Button type="submit" disabled={mutation.isPending}>
            {t('goalResult.registerButton')}
          </Button>
        </div>
      </form>
    </Card>
  )
}

/** SC-10 受験結果登録（仕様書6.9）。 */
export function ExamResultPage() {
  const { goalId: goalIdParam } = useParams<{ goalId: string }>()
  const goalId = Number(goalIdParam)
  const navigate = useNavigate()
  const [closeModalOpen, setCloseModalOpen] = useState(false)

  const goalQuery = useQuery({ queryKey: ['goal', goalId], queryFn: () => getGoal(goalId) })

  if (goalQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (goalQuery.isError || !goalQuery.data) {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(goalQuery.error)}</p>
  }

  const goal = goalQuery.data
  if (isClosedGoalStatus(goal.status)) {
    return <Navigate to={ROUTES.goalExport(goal.id)} replace />
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <Link to={ROUTES.goalDetail(goal.id)} className="text-sm text-blue-600 hover:underline">
        {t('goalResult.backToGoal')}
      </Link>

      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">
          {t('goalResult.title', { name: goal.name })}
        </h1>
        <Button variant="secondary" onClick={() => setCloseModalOpen(true)}>
          {t('goals.detail.action.close')}
        </Button>
      </div>

      {goal.exam_subjects.length === 0 && (
        <p className="text-sm text-gray-500">{t('goalResult.empty')}</p>
      )}

      {goal.exam_subjects.map((subject) => (
        <ExamResultForm key={subject.id} goalId={goal.id} subject={subject} />
      ))}

      <CloseGoalModal
        goalId={goal.id}
        open={closeModalOpen}
        onClose={() => setCloseModalOpen(false)}
        onClosed={() => {
          // 総括レポートの生成はクローズ処理の成否に影響させない（仕様書6.9・実装フェーズ
          // 分割計画書Phase10注意点「非同期で実行し、失敗しても後から再生成できるようにする」）。
          // 失敗時もSC-13へは遷移し、同画面の生成ボタンから再試行できる。
          generateRetrospective(goal.id, false).catch(() => undefined)
          navigate(ROUTES.goalExport(goal.id))
        }}
      />
    </div>
  )
}

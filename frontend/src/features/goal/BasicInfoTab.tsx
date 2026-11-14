import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { CollapsibleSection } from '../../components/CollapsibleSection'
import { useToast } from '../../components/toastContext'
import { updateGoal, type GoalDetailRead } from '../../api/goals'
import { resolveByGoalCategory } from './goalCategoryVariant'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { SummaryCardSection } from '../summaryCard/SummaryCardSection'

/** 基本情報タブ（仕様書6.2「試験名、開始日、状態、備考」）。 */
export function BasicInfoTab({ goal, readOnly }: { goal: GoalDetailRead; readOnly: boolean }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const [name, setName] = useState(goal.name)
  const [startDate, setStartDate] = useState(goal.start_date)
  const [memo, setMemo] = useState(goal.memo ?? '')

  const mutation = useMutation({
    mutationFn: () => updateGoal(goal.id, { name, start_date: startDate, memo }),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.goal(goal.id) })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const nameLabel = t(
    resolveByGoalCategory(goal.category, {
      EXAM: 'goals.basicInfo.nameLabel',
      READING: 'goals.basicInfo.nameLabelReading',
      WORK: 'goals.basicInfo.nameLabelWork',
    }),
  )

  return (
    <>
      <Card className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {nameLabel}
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={readOnly}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('goals.basicInfo.startDateLabel')}
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            disabled={readOnly}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('goals.basicInfo.memoLabel')}
          <textarea
            className="rounded-md border border-border-strong px-3 py-2 text-sm focus:border-accent focus:outline-none"
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            disabled={readOnly}
            rows={3}
          />
        </label>
        {!readOnly && (
          <div className="flex justify-end">
            <Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>
              {t('common.action.save')}
            </Button>
          </div>
        )}
      </Card>
      {/* ふりかえりまとめ・共有カードは開くまでマウントしない（パフォーマンスレビュー指摘、
          2026-11-13）。基本情報タブは目標詳細画面の既定タブのため、常時マウントすると
          `GET /records/today`→`GET /goals/{id}/summary-card`の直列2往復が、カードを
          一度も見ない利用者にも毎回発生してしまう。既存の`CollapsibleSection`（明示操作
          まで中身をレンダーしない既定折りたたみ部品）をそのまま再利用する（CLAUDE.md
          DRYの原則。新規の開閉コンポーネントは作らない）。 */}
      <CollapsibleSection
        title={t('summaryCard.openButton')}
        hiddenTitle={t('common.action.close')}
      >
        <SummaryCardSection
          goalId={goal.id}
          goalName={goal.name}
          category={goal.category}
          mode="open"
        />
      </CollapsibleSection>
    </>
  )
}

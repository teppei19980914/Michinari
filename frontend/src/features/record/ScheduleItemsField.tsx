import type { Dispatch, SetStateAction } from 'react'
import { t } from '../../locales/t'
import { ScheduleItemsGoalGroup } from './ScheduleItemsGoalGroup'
import type { GoalScheduleItemsForReportRead } from '../../api/records'
import type { ScheduleItemDraftValue } from './scheduleItemsDraft'

/**
 * 日次報告・進捗のみ登録の「今日の作業項目」欄（開発Todo_スケジュール・ガントチャート_v1.1
 * 第4章・D-32〜D-39、単位4）。
 *
 * 配置は各種別の実績入力の直下（D-38）。作業項目が1件も無い目標では欄ごと表示しない
 * （`goals`は呼び出し側で既に「対象になる行が1件以上ある目標」だけに絞り込まれている、
 * `schedule_service.list_schedule_items_for_report`参照）ため、ここでは`goals`が空か
 * どうかだけを見る。
 *
 * 日次報告（SC-06）では目標タブの絞り込みにより通常0〜1目標分だけが渡るが、進捗のみ登録
 * （SC-07）は目標タブを持たず全カテゴリを一度に表示するため複数目標分が渡りうる
 * （ProgressOnlyPage.tsx参照）。
 */
export function ScheduleItemsField({
  goals,
  targetDate,
  readOnly,
  values,
  onChange,
}: {
  goals: GoalScheduleItemsForReportRead[]
  targetDate: string
  readOnly: boolean
  values: Record<number, ScheduleItemDraftValue>
  onChange: Dispatch<SetStateAction<Record<number, ScheduleItemDraftValue>>>
}) {
  if (goals.length === 0) {
    return null
  }

  const handleItemChange = (itemId: number, next: ScheduleItemDraftValue) =>
    onChange((current) => ({ ...current, [itemId]: next }))

  return (
    <div className="flex flex-col gap-4 rounded-md border border-border-subtle p-3">
      <h3 className="text-sm font-medium text-text-primary">
        {t('schedule.dailyReportSection.title')}
      </h3>
      {goals.map((goal) => (
        <ScheduleItemsGoalGroup
          key={goal.goal_id}
          goal={goal}
          targetDate={targetDate}
          readOnly={readOnly}
          values={values}
          onChange={handleItemChange}
        />
      ))}
    </div>
  )
}

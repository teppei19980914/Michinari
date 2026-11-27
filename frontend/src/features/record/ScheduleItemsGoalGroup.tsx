import { useState } from 'react'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { ScheduleItemRow } from './ScheduleItemRow'
import type { GoalScheduleItemsForReportRead } from '../../api/records'
import type { ScheduleItemDraftValue } from './scheduleItemsDraft'

/**
 * 「今日の作業項目」欄の1目標分（開発Todo_スケジュール・ガントチャート_v1.1 第4章、単位4）。
 *
 * 入力中（`readOnly=false`）は、既定でD-33の3条件（報告対象日が予定期間内／進行中／
 * 予定終了日を過ぎた未完了）に該当する行（`default_visible`）のみを表示し、「すべて表示」
 * で完了・中止以外の全行へ展開する（12章補足7。完了・中止の行はGET /records/{date}/
 * schedule-itemsの応答にそもそも含まれないため、ここでは絞り込みのみを行う）。
 *
 * 確定済み（`readOnly=true`）は`CategoryScheduleItemsField`がGET /records/{date}/
 * schedule-items-historyの応答（その日に更新した行。完了・中止を含む）を渡す。この応答は
 * 全行`default_visible=true`のため、本関数の絞り込みは素通りし「すべて表示」も出ない
 * （軽微な修正3、開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md）。
 */
export function ScheduleItemsGoalGroup({
  goal,
  targetDate,
  readOnly,
  values,
  onChange,
}: {
  goal: GoalScheduleItemsForReportRead
  targetDate: string
  readOnly: boolean
  values: Record<number, ScheduleItemDraftValue>
  onChange: (itemId: number, next: ScheduleItemDraftValue) => void
}) {
  const [showAll, setShowAll] = useState(false)
  const visibleItems = goal.items.filter((item) => showAll || item.default_visible)
  const hasHiddenItems = goal.items.some((item) => !item.default_visible)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-text-primary">{goal.goal_name}</h3>
        {hasHiddenItems && (
          <Button variant="secondary" onClick={() => setShowAll((current) => !current)}>
            {showAll ? t('schedule.dailyReportSection.collapse') : t('schedule.dailyReportSection.showAll')}
          </Button>
        )}
      </div>
      {visibleItems.length === 0 && (
        <p className="text-xs text-text-faint">{t('schedule.dailyReportSection.noRows')}</p>
      )}
      {visibleItems.map((item) => {
        // readOnlyの場合は取得結果（確定済みの最新値）をそのまま使う。下書きは編集時のみ
        // 参照する（ScheduleItemRowのJSDoc参照）。未hydrate等でvaluesに無い場合も
        // 取得結果の値で補う（defensive、通常は到達しない）。
        const value: ScheduleItemDraftValue = values[item.id] ?? {
          status: item.status,
          actualStartDate: item.actual_start_date,
          actualEndDate: item.actual_end_date,
          touched: false,
        }
        return (
          <ScheduleItemRow
            key={item.id}
            item={item}
            targetDate={targetDate}
            readOnly={readOnly}
            value={value}
            onChange={(next) => onChange(item.id, next)}
          />
        )
      })}
    </div>
  )
}

import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { ScheduleStatusSelect } from '../schedule/ScheduleStatusSelect'
import { applyScheduleStatusAutoFill } from '../schedule/scheduleStatusAutoFill'
import { validateScheduleItemFields } from '../schedule/scheduleValidation'
import type { ScheduleItemForReportRead } from '../../api/records'
import type { ScheduleItemStatus } from '../../api/schedule'
import type { ScheduleItemDraftValue } from './scheduleItemsDraft'

/** 「今日の作業項目」欄の1行分（開発Todo_スケジュール・ガントチャート_v1.1 第4章、単位4）。
 *
 * 作業項目・作業内容・予定日はこの欄からは変更できない（本書8章、確定API3本・progress APIが
 * 受け付けるのは状況・実績日のみ）。状況変更時の実績日の補完は、スケジュール画面（単位3）と
 * 同じ`applyScheduleStatusAutoFill`を基準日=報告対象日で呼ぶ（6.3）。検証も同じ
 * `validateScheduleItemFields`を再利用し、重複実装しない（6.1）。
 */
export function ScheduleItemRow({
  item,
  targetDate,
  readOnly,
  value,
  onChange,
}: {
  item: ScheduleItemForReportRead
  targetDate: string
  readOnly: boolean
  value: ScheduleItemDraftValue
  onChange: (next: ScheduleItemDraftValue) => void
}) {
  const errors = validateScheduleItemFields(
    {
      title: item.title,
      plannedStartDate: item.planned_start_date,
      plannedEndDate: item.planned_end_date,
      status: value.status,
      actualStartDate: value.actualStartDate,
      actualEndDate: value.actualEndDate,
    },
    targetDate,
  )

  const handleStatusChange = (nextStatus: ScheduleItemStatus) => {
    const filled = applyScheduleStatusAutoFill(
      nextStatus,
      { actualStartDate: value.actualStartDate, actualEndDate: value.actualEndDate },
      targetDate,
    )
    onChange({ ...filled, status: nextStatus, touched: true })
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border-subtle p-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col">
        <span className="text-sm text-text-primary">{item.title}</span>
        <span className="text-xs text-text-faint">
          {t('schedule.gantt.tooltip.planned', {
            start: item.planned_start_date,
            end: item.planned_end_date,
          })}
        </span>
      </div>
      {readOnly ? (
        <ScheduleItemReadOnlyStatus item={item} />
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <ScheduleStatusSelect value={value.status} disabled={false} onChange={handleStatusChange} />
          <Input
            type="date"
            value={value.actualStartDate ?? ''}
            disabled={value.status === 'NOT_STARTED'}
            aria-label={t('schedule.columns.actualStartDate')}
            onChange={(event) =>
              onChange({ ...value, actualStartDate: event.target.value || null, touched: true })
            }
            className={errors.actualStartDate ? 'border-danger-text' : ''}
          />
          <Input
            type="date"
            value={value.actualEndDate ?? ''}
            disabled={value.status === 'NOT_STARTED' || value.status === 'IN_PROGRESS'}
            aria-label={t('schedule.columns.actualEndDate')}
            onChange={(event) =>
              onChange({ ...value, actualEndDate: event.target.value || null, touched: true })
            }
            className={errors.actualEndDate ? 'border-danger-text' : ''}
          />
        </div>
      )}
    </div>
  )
}

/** 確定済みの種別での読み取り専用表示（12章補足6「その日に更新した作業項目を読み取り専用で
 * 表示する」）。下書きではなく取得結果（確定済みの最新値）をそのまま表示する。 */
function ScheduleItemReadOnlyStatus({ item }: { item: ScheduleItemForReportRead }) {
  return (
    <div className="flex items-center gap-3 text-xs text-text-faint">
      <span>{t(`schedule.status.${item.status}`)}</span>
      <span>
        {item.actual_start_date || item.actual_end_date
          ? t('schedule.gantt.tooltip.actual', {
              // 実績終了日のみが入力された状態は6.2の検証（validate_item_fields）が
              // 拒否するため、actual_start_date側の`?? '—'`は到達しない防御的分岐
              // （OPERATIONS.md「到達不能な防御的分岐」）。
              /* v8 ignore next */
              start: item.actual_start_date ?? '—',
              end: item.actual_end_date ?? '—',
            })
          : t('schedule.gantt.tooltip.noActual')}
      </span>
    </div>
  )
}

import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { t } from '../../locales/t'
import type { ScheduleRevisionProposalItemRead } from '../../api/schedule'

/**
 * 修正案の変更行（開発Todo_スケジュール・ガントチャート_v1.1 13.8、単位5）。
 *
 * 承認前に日付を手で修正できる（D-56）。変更前の値が現在のスケジュールと一致しない行
 * （`is_stale`、D-59）はボタンを押せないようにし、専用の文言を表示する。
 *
 * `blockedReason`（修正1、開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md）は
 * 直前の承認が13.5の制約（新しい予定日は本日以降等）に反してブロックされたことを示す。
 * `is_stale`と異なりボタンは無効化しない。利用者が日付を修正して再度承認できるようにする。
 */
export function ScheduleRevisionChangeRow({
  item,
  title,
  disabled,
  dates,
  rejectReason,
  blockedReason,
  onChangeDates,
  onChangeRejectReason,
  onApprove,
  onReject,
}: {
  item: ScheduleRevisionProposalItemRead
  title: string
  disabled: boolean
  dates: { start: string; end: string }
  rejectReason: string
  blockedReason?: string | null
  onChangeDates: (dates: { start: string; end: string }) => void
  onChangeRejectReason: (reason: string) => void
  onApprove: () => void
  onReject: () => void
}) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border bg-surface p-2">
      <p className="text-sm font-medium text-text-primary">{title}</p>
      <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
        <span>
          {t('schedule.revision.before', {
            start: item.before_planned_start_date,
            end: item.before_planned_end_date,
          })}
        </span>
        <span aria-hidden="true">→</span>
        <Input
          type="date"
          aria-label={t('schedule.revision.proposedStartDate')}
          value={dates.start}
          disabled={disabled}
          onChange={(event) => onChangeDates({ ...dates, start: event.target.value })}
          className="text-xs"
        />
        <Input
          type="date"
          aria-label={t('schedule.revision.proposedEndDate')}
          value={dates.end}
          disabled={disabled}
          onChange={(event) => onChangeDates({ ...dates, end: event.target.value })}
          className="text-xs"
        />
      </div>
      <p className="text-xs text-text-muted">{item.reason}</p>
      {item.is_stale ? (
        <p className="text-xs text-danger-text">{t('schedule.revision.staleBeforeValue')}</p>
      ) : (
        <>
          {blockedReason && (
            <p className="text-xs text-danger-text">{t('schedule.revision.invalidPlannedDate')}</p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="primary" disabled={disabled} onClick={onApprove}>
              {t('schedule.revision.approve')}
            </Button>
            <Input
              type="text"
              placeholder={t('schedule.revision.rejectReasonPlaceholder')}
              aria-label={t('schedule.revision.rejectReasonPlaceholder')}
              value={rejectReason}
              disabled={disabled}
              onChange={(event) => onChangeRejectReason(event.target.value)}
              className="text-xs"
            />
            <Button variant="secondary" disabled={disabled} onClick={onReject}>
              {t('schedule.revision.reject')}
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

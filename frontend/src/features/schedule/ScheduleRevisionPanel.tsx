import { useState } from 'react'
import { Button } from '../../components/Button'
import { t } from '../../locales/t'
import type {
  ScheduleRevisionDecisionInput,
  ScheduleRevisionProposalItemRead,
  ScheduleRevisionProposalRead,
} from '../../api/schedule'
import { ScheduleRevisionChangeRow } from './ScheduleRevisionChangeRow'
import { ScheduleRevisionWarningRow } from './ScheduleRevisionWarningRow'
import type { EditedDates } from './useScheduleRevisionEditedDates'

/**
 * スケジュールタブの修正案パネル（開発Todo_スケジュール・ガントチャート_v1.1 13.8、単位5）。
 *
 * 未判断（PENDING）の行だけを表示する。表に未保存の変更があるとき（`canDecide=false`）は
 * 承認・却下・確認済みのボタンをすべて無効化する（承認でrevisionが変わり、未保存の編集が
 * 409になるのを防ぐ、13.8）。承認前の日付修正（D-56）は`ScheduleTab`と共有する
 * `useScheduleRevisionEditedDates`で保持し、ガントの点線重ね表示（D-57）にも同じ値を渡す。
 */
export function ScheduleRevisionPanel({
  proposal,
  itemTitleById,
  canDecide,
  isDeciding,
  datesFor,
  setDates,
  onDecide,
}: {
  proposal: ScheduleRevisionProposalRead
  itemTitleById: Record<number, string>
  canDecide: boolean
  isDeciding: boolean
  datesFor: (item: ScheduleRevisionProposalItemRead) => EditedDates
  setDates: (itemId: number, dates: EditedDates) => void
  onDecide: (decisions: ScheduleRevisionDecisionInput[]) => void
}) {
  const [rejectReasons, setRejectReasons] = useState<Record<number, string>>({})

  const pendingChangeItems = proposal.items.filter(
    (item) => item.kind === 'CHANGE' && item.decision === 'PENDING',
  )
  const pendingWarningItems = proposal.items.filter(
    (item) => item.kind === 'WARNING' && item.decision === 'PENDING',
  )

  if (pendingChangeItems.length === 0 && pendingWarningItems.length === 0) {
    return null
  }

  const disabled = !canDecide || isDeciding

  function approve(item: ScheduleRevisionProposalItemRead) {
    const dates = datesFor(item)
    onDecide([
      {
        proposal_item_id: item.id,
        decision: 'APPROVED',
        planned_start_date: dates.start,
        planned_end_date: dates.end,
      },
    ])
  }

  function reject(item: ScheduleRevisionProposalItemRead) {
    onDecide([
      {
        proposal_item_id: item.id,
        decision: 'REJECTED',
        reject_reason: rejectReasons[item.id] || null,
      },
    ])
  }

  function acknowledge(item: ScheduleRevisionProposalItemRead) {
    onDecide([{ proposal_item_id: item.id, decision: 'ACKNOWLEDGED' }])
  }

  function approveAll() {
    const decisions: ScheduleRevisionDecisionInput[] = pendingChangeItems
      .filter((item) => !item.is_stale)
      .map((item) => {
        const dates = datesFor(item)
        return {
          proposal_item_id: item.id,
          decision: 'APPROVED',
          planned_start_date: dates.start,
          planned_end_date: dates.end,
        }
      })
    if (decisions.length > 0) onDecide(decisions)
  }

  function rejectAll() {
    const decisions: ScheduleRevisionDecisionInput[] = pendingChangeItems
      .filter((item) => !item.is_stale)
      .map((item) => ({
        proposal_item_id: item.id,
        decision: 'REJECTED',
        reject_reason: rejectReasons[item.id] || null,
      }))
    if (decisions.length > 0) onDecide(decisions)
  }

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border bg-surface-muted p-3">
      <p className="text-sm font-medium text-text-primary">{t('schedule.revision.title')}</p>
      {proposal.summary && <p className="text-sm text-text-secondary">{proposal.summary}</p>}
      {!canDecide && (
        <p className="text-xs text-warning-text">{t('schedule.revision.saveOrDiscardFirst')}</p>
      )}
      {pendingChangeItems.length > 0 && (
        <div className="flex flex-col gap-2">
          {pendingChangeItems.map((item) => (
            <ScheduleRevisionChangeRow
              key={item.id}
              item={item}
              title={itemTitleById[item.schedule_item_id] ?? ''}
              disabled={disabled || item.is_stale}
              dates={datesFor(item)}
              rejectReason={rejectReasons[item.id] ?? ''}
              onChangeDates={(dates) => setDates(item.id, dates)}
              onChangeRejectReason={(reason) =>
                setRejectReasons((prev) => ({ ...prev, [item.id]: reason }))
              }
              onApprove={() => approve(item)}
              onReject={() => reject(item)}
            />
          ))}
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" disabled={disabled} onClick={approveAll}>
              {t('schedule.revision.approveAll')}
            </Button>
            <Button variant="secondary" disabled={disabled} onClick={rejectAll}>
              {t('schedule.revision.rejectAll')}
            </Button>
          </div>
        </div>
      )}
      {pendingWarningItems.length > 0 && (
        <div className="flex flex-col gap-2">
          {pendingWarningItems.map((item) => (
            <ScheduleRevisionWarningRow
              key={item.id}
              item={item}
              title={itemTitleById[item.schedule_item_id] ?? ''}
              disabled={disabled}
              onAcknowledge={() => acknowledge(item)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

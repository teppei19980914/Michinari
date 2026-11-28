import { Button } from '../../components/Button'
import { t } from '../../locales/t'
import type {
  ScheduleRevisionDecisionInput,
  ScheduleRevisionProposalItemRead,
  ScheduleRevisionProposalRead,
} from '../../api/schedule'
import { ScheduleRevisionChangeRow } from './ScheduleRevisionChangeRow'
import { ScheduleRevisionWarningRow } from './ScheduleRevisionWarningRow'
import { useScheduleRevisionPanelActions } from './useScheduleRevisionPanelActions'
import type { EditedDates } from './useScheduleRevisionEditedDates'

/**
 * スケジュールタブの修正案パネル（開発Todo_スケジュール・ガントチャート_v1.1 13.8、単位5）。
 *
 * 未判断（PENDING）の行だけを表示する。表に未保存の変更があるとき（`canDecide=false`）は
 * 承認・却下・確認済みのボタンをすべて無効化する（承認でrevisionが変わり、未保存の編集が
 * 409になるのを防ぐ、13.8）。承認前の日付修正（D-56）は`ScheduleTab`と共有する
 * `useScheduleRevisionEditedDates`で保持し、ガントの点線重ね表示（D-57）にも同じ値を渡す。
 * 判断ハンドラ自体は`useScheduleRevisionPanelActions`へ分離している（複雑度対策）。
 * `blockedReasonFor`（省略時は常に`null`）は、直前の承認が13.5の制約でブロックされた行
 * （修正1、開発Todo_スケジュール・ガントチャート_検証修正_v1.0.md）の理由を返す。
 *
 * `readOnly`（終了した目標、`isClosedGoalStatus`。軽微な修正1、開発Todo_スケジュール・
 * ガントチャート_検証修正_v1.0.md）が真のときは、承認・却下・確認済みのボタンを一切
 * 表示しない（閲覧のみ）。`canDecide=false`時の無効化（表示はするが押せない）とは異なる。
 */
export function ScheduleRevisionPanel({
  proposal,
  itemTitleById,
  canDecide,
  isDeciding,
  readOnly = false,
  datesFor,
  setDates,
  onDecide,
  blockedReasonFor = () => null,
}: {
  proposal: ScheduleRevisionProposalRead
  itemTitleById: Record<number, string>
  canDecide: boolean
  isDeciding: boolean
  readOnly?: boolean
  datesFor: (item: ScheduleRevisionProposalItemRead) => EditedDates
  setDates: (itemId: number, dates: EditedDates) => void
  onDecide: (decisions: ScheduleRevisionDecisionInput[]) => void
  blockedReasonFor?: (itemId: number) => string | null
}) {
  const pendingChangeItems = proposal.items.filter(
    (item) => item.kind === 'CHANGE' && item.decision === 'PENDING',
  )
  const pendingWarningItems = proposal.items.filter(
    (item) => item.kind === 'WARNING' && item.decision === 'PENDING',
  )
  const { rejectReasons, setRejectReason, approve, reject, acknowledge, approveAll, rejectAll } =
    useScheduleRevisionPanelActions(pendingChangeItems, datesFor, onDecide, blockedReasonFor)

  if (pendingChangeItems.length === 0 && pendingWarningItems.length === 0) {
    return null
  }

  const disabled = !canDecide || isDeciding

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border bg-surface-muted p-3">
      <p className="text-sm font-medium text-text-primary">{t('schedule.revision.title')}</p>
      {proposal.summary && <p className="text-sm text-text-secondary">{proposal.summary}</p>}
      {!canDecide && !readOnly && (
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
              readOnly={readOnly}
              dates={datesFor(item)}
              rejectReason={rejectReasons[item.id] ?? ''}
              blockedReason={blockedReasonFor(item.id)}
              onChangeDates={(dates) => setDates(item.id, dates)}
              onChangeRejectReason={(reason) => setRejectReason(item.id, reason)}
              onApprove={() => approve(item)}
              onReject={() => reject(item)}
            />
          ))}
          {!readOnly && (
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" disabled={disabled} onClick={approveAll}>
                {t('schedule.revision.approveAll')}
              </Button>
              <Button variant="secondary" disabled={disabled} onClick={rejectAll}>
                {t('schedule.revision.rejectAll')}
              </Button>
            </div>
          )}
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
              readOnly={readOnly}
              onAcknowledge={() => acknowledge(item)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

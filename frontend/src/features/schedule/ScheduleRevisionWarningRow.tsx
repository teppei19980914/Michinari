import { Button } from '../../components/Button'
import { t } from '../../locales/t'
import type { ScheduleRevisionProposalItemRead } from '../../api/schedule'

/**
 * 修正案の注意行（期限内に収まらない等、開発Todo_スケジュール・ガントチャート_v1.1
 * 13.8、単位5）。承認・却下の対象ではなく「確認しました」で閉じる（decision=ACKNOWLEDGED）。
 */
export function ScheduleRevisionWarningRow({
  item,
  title,
  disabled,
  onAcknowledge,
}: {
  item: ScheduleRevisionProposalItemRead
  title: string
  disabled: boolean
  onAcknowledge: () => void
}) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-warning-text bg-surface p-2">
      <p className="text-sm font-medium text-text-primary">{title}</p>
      <p className="text-xs text-text-muted">{item.reason}</p>
      <div>
        <Button variant="secondary" disabled={disabled} onClick={onAcknowledge}>
          {t('schedule.revision.acknowledge')}
        </Button>
      </div>
    </div>
  )
}

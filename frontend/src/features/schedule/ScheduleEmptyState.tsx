import { t } from '../../locales/t'
import { Button } from '../../components/Button'

/** 行が0件のときの案内（D-28）。閲覧のみの目標では「行を追加」を出さない。 */
export function ScheduleEmptyState({
  readOnly,
  onAddRow,
}: {
  readOnly: boolean
  onAddRow: () => void
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-md border border-dashed border-border-strong bg-surface-muted p-8 text-center">
      <p className="text-sm font-medium text-text-primary">{t('schedule.empty.title')}</p>
      <p className="text-sm text-text-muted">{t('schedule.empty.description')}</p>
      {!readOnly && (
        <Button variant="primary" onClick={onAddRow}>
          {t('schedule.toolbar.addRow')}
        </Button>
      )}
    </div>
  )
}

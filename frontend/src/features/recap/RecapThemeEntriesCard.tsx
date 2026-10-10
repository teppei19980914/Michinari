import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { RecapThemeDetail } from '../../api/recap'

type RecapThemeEntry = RecapThemeDetail['entries'][number]

/** テーマに紐付く報告の一覧（日付順、各報告は元の日記・想起記録の本文を表示する）。 */
export function RecapThemeEntriesCard({ entries }: { entries: RecapThemeEntry[] }) {
  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-text-primary">{t('recapTheme.entriesTitle')}</h2>
      {entries.length === 0 && <p className="text-sm text-text-faint">{t('recapTheme.entriesEmpty')}</p>}
      {entries.map((entry, index) => (
        <div key={`${entry.source_kind}-${entry.record_date}-${index}`} className="border-t pt-2">
          <p className="text-xs text-text-disabled">
            {entry.record_date} · {t(`recapTheme.sourceKind.${entry.source_kind}`)}
          </p>
          <p className="whitespace-pre-wrap text-sm text-text-primary">{entry.text}</p>
        </div>
      ))}
    </Card>
  )
}

import { useState } from 'react'
import { t } from '../../locales/t'
import type { PreviousEntryRead } from '../../api/records'
import { buildPreviousEntryPreview } from './previousEntryPreview'

/**
 * 「前回はこう書いていました」ヒント（仕様書6.5改、記録画面改善タスク2026-09-17）。
 * 前回の記録が無い場合（entryがnull/undefined）は何も表示しない。
 */
export function PreviousEntryHint({ entry }: { entry: PreviousEntryRead | null | undefined }) {
  const [expanded, setExpanded] = useState(false)

  if (!entry) {
    return null
  }

  const { preview, isTruncated } = buildPreviousEntryPreview(entry.body)

  return (
    <div className="rounded-md bg-surface-muted px-3 py-2 text-xs text-text-faint">
      <p className="font-medium text-text-disabled">{t('dailyReport.previousEntry.label')}</p>
      <p className="mt-1 whitespace-pre-wrap">
        {expanded ? entry.body : preview}
        {!expanded && isTruncated ? '…' : ''}
      </p>
      {isTruncated && (
        <button
          type="button"
          className="mt-1 text-accent underline"
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? t('dailyReport.previousEntry.collapse') : t('dailyReport.previousEntry.expand')}
        </button>
      )}
    </div>
  )
}

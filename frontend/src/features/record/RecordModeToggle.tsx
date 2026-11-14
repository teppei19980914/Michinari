import { t } from '../../locales/t'
import type { RecordInputMode } from './recordInputMode'

export type RecordModeToggleProps = {
  mode: RecordInputMode
  onChange: (mode: RecordInputMode) => void
}

/** 通常入力／ひとこと記録モードの切替（開発Todo「ひとこと記録」v1.0 §4.1手順1）。 */
export function RecordModeToggle({ mode, onChange }: RecordModeToggleProps) {
  return (
    <div className="inline-flex gap-1 rounded-md border border-border p-1" role="group">
      {(['NORMAL', 'QUICK'] as const).map((candidate) => (
        <button
          key={candidate}
          type="button"
          aria-pressed={mode === candidate}
          onClick={() => onChange(candidate)}
          className={`rounded-md px-3 py-1 text-xs font-medium ${
            mode === candidate
              ? 'bg-accent text-accent-muted-text'
              : 'text-text-faint hover:text-text-secondary'
          }`}
        >
          {t(
            candidate === 'QUICK'
              ? 'dailyReport.quickRecord.modeToggle.quick'
              : 'dailyReport.quickRecord.modeToggle.normal',
          )}
        </button>
      ))}
    </div>
  )
}

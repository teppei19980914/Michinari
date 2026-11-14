import { t } from '../../locales/t'
import { MOOD_VALUES, type MoodValue } from './moodStamps'

export type MoodStampPickerProps = {
  value: MoodValue | null
  onChange: (value: MoodValue) => void
}

/** 気分スタンプ選択（ひとこと記録モード、開発Todo「ひとこと記録」v1.0 決定事項D1・Q6）。
 * 5段階固定、絵文字＋ラベル併記。選択済みのスタンプのみ強調表示する。 */
export function MoodStampPicker({ value, onChange }: MoodStampPickerProps) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm text-text-secondary">{t('dailyReport.quickRecord.moodLabel')}</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label={t('dailyReport.quickRecord.moodLabel')}>
        {MOOD_VALUES.map((moodValue) => (
          <button
            key={moodValue}
            type="button"
            aria-pressed={value === moodValue}
            onClick={() => onChange(moodValue)}
            className={`rounded-md border px-3 py-2 text-sm ${
              value === moodValue
                ? 'border-accent bg-accent-muted-bg text-accent-muted-text'
                : 'border-border text-text-secondary hover:bg-surface-muted'
            }`}
          >
            {t(`dailyReport.quickRecord.moodStamps.${moodValue}`)}
          </button>
        ))}
      </div>
    </div>
  )
}

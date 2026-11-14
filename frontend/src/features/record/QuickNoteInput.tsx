import { t } from '../../locales/t'
import { Input } from '../../components/Input'

export type QuickNoteInputProps = {
  value: string
  onChange: (value: string) => void
  /** 1行メモの最大文字数（`quick_record.note_max_chars`、設定画面から変更可能）。 */
  maxChars: number
}

/** 1行メモ入力（ひとこと記録モード、開発Todo「ひとこと記録」v1.0 決定事項D3）。
 * 保存先はカテゴリごとの既存の自由記述欄（diaryLearned/freeText）と同じのため
 * （新規DB列は不要）、本コンポーネントは入力欄の見た目のみを担う。 */
export function QuickNoteInput({ value, onChange, maxChars }: QuickNoteInputProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('dailyReport.quickRecord.noteLabel')}
        <Input
          type="text"
          maxLength={maxChars}
          placeholder={t('dailyReport.quickRecord.notePlaceholder')}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
      <span className="text-xs text-text-disabled">
        {t('dailyReport.quickRecord.noteCounter', { current: value.length, max: maxChars })}
      </span>
    </div>
  )
}

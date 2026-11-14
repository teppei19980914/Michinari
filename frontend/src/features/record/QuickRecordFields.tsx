import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { MoodStampPicker } from './MoodStampPicker'
import { QuickNoteInput } from './QuickNoteInput'
import { VoiceInputHint } from './VoiceInputHint'
import type { MoodValue } from './moodStamps'

export type QuickRecordFieldsProps = {
  note: string
  onChangeNote: (value: string) => void
  mood: MoodValue | null
  onChangeMood: (value: MoodValue) => void
  /** 1行メモの最大文字数（`quick_record.note_max_chars`）。 */
  maxChars: number
  /** 資格試験のみ、学習量（完了量・時間）が記録されないことを明示する（開発Todo
   * 「ひとこと記録」v1.0 §6の既知のリスク対策）。 */
  showNumbersSkippedNotice: boolean
}

/** ひとこと記録モードの編集欄（気分スタンプ＋1行メモだけで確定できる、開発Todo
 * 「ひとこと記録」v1.0 決定事項D1）。保存先は通常モードと同じ自由記述欄
 * （diaryLearned/freeText）のため、本コンポーネント自体はDBへの保存経路を持たない。 */
export function QuickRecordFields({
  note,
  onChangeNote,
  mood,
  onChangeMood,
  maxChars,
  showNumbersSkippedNotice,
}: QuickRecordFieldsProps) {
  return (
    <Card className="flex flex-col gap-3">
      {showNumbersSkippedNotice && (
        <p className="text-xs text-text-disabled">
          {t('dailyReport.quickRecord.numbersSkippedNotice')}
        </p>
      )}
      <MoodStampPicker value={mood} onChange={onChangeMood} />
      <QuickNoteInput value={note} onChange={onChangeNote} maxChars={maxChars} />
      <VoiceInputHint />
    </Card>
  )
}

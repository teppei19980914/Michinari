/** 受験結果の入力欄（SC-10 ExamResultPage の ExamResultForm）。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた ExamResultForm から、
 * 入力欄の並びを切り出したものである。入力値の保持と送信内容の判定（任意項目の空欄を
 * `null` にする・既存の有無で登録と更新を呼び分ける）は呼び出し元に残す。 */
import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import { RESULT_TYPES, type ExamResultType } from './examResultOptions'

export function ExamResultFields({
  takenDate,
  onChangeTakenDate,
  result,
  onChangeResult,
  score,
  onChangeScore,
  evaluation,
  onChangeEvaluation,
  note,
  onChangeNote,
}: {
  takenDate: string
  onChangeTakenDate: (value: string) => void
  result: ExamResultType
  onChangeResult: (value: ExamResultType) => void
  score: string
  onChangeScore: (value: string) => void
  evaluation: string
  onChangeEvaluation: (value: string) => void
  note: string
  onChangeNote: (value: string) => void
}) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goalResult.takenDateLabel')}
        <Input
          type="date"
          value={takenDate}
          onChange={(e) => onChangeTakenDate(e.target.value)}
          required
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goalResult.resultLabel')}
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={result}
          onChange={(e) => onChangeResult(e.target.value as ExamResultType)}
        >
          {RESULT_TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`goalResult.result.${value}`)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goalResult.scoreLabel')}
        <Input type="number" value={score} onChange={(e) => onChangeScore(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goalResult.evaluationLabel')}
        <Input value={evaluation} onChange={(e) => onChangeEvaluation(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goalResult.noteLabel')}
        <Textarea rows={3} value={note} onChange={(e) => onChangeNote(e.target.value)} />
      </label>
    </>
  )
}

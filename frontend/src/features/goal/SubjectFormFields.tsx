/** 試験科目フォーム（SubjectsTab.tsx の SubjectForm）の入力欄を切り出した表示部品。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた SubjectForm から、
 * 受験日欄と合格基準欄を切り出したものである。どちらも「種別の選択に応じて入力欄を
 * 差し替える」という同じ形をしているため、ここへまとめて置く。
 *
 * 送信内容の判定（種別に合わない側の値を`null`にする）は SubjectForm と passingScore.ts に
 * 残す。ここは表示と入力の受け渡しに徹する。 */
import { t } from '../../locales/t'
import { Input } from '../../components/Input'
import { Tooltip } from '../../components/Tooltip'
import type { PassingScoreFormState, PassingScoreType } from './passingScore'
import {
  EXAM_DATE_TYPES,
  PASSING_SCORE_TYPES,
  type ExamDateType,
} from './subjectOptions'

/** 受験日の指定方法と、その方法に応じた日付入力欄（範囲なら開始・終了、確定日なら1つ）。 */
export function SubjectExamDateFields({
  examDateType,
  onChangeExamDateType,
  examDateFrom,
  onChangeExamDateFrom,
  examDateTo,
  onChangeExamDateTo,
  examDateFixed,
  onChangeExamDateFixed,
}: {
  examDateType: ExamDateType
  onChangeExamDateType: (value: ExamDateType) => void
  examDateFrom: string
  onChangeExamDateFrom: (value: string) => void
  examDateTo: string
  onChangeExamDateTo: (value: string) => void
  examDateFixed: string
  onChangeExamDateFixed: (value: string) => void
}) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        <Tooltip label={t('goals.subjects.examDateTypeTooltip')}>
          <span>{t('goals.subjects.examDateTypeLabel')}</span>
        </Tooltip>
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={examDateType}
          onChange={(e) => onChangeExamDateType(e.target.value as ExamDateType)}
        >
          {EXAM_DATE_TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`goals.subjects.examDateType.${value}`)}
            </option>
          ))}
        </select>
      </label>
      {examDateType === 'RANGE' ? (
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.subjects.examDateFromLabel')}
            <Input
              type="date"
              value={examDateFrom}
              onChange={(e) => onChangeExamDateFrom(e.target.value)}
              required
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.subjects.examDateToLabel')}
            <Input
              type="date"
              value={examDateTo}
              onChange={(e) => onChangeExamDateTo(e.target.value)}
              required
            />
          </label>
        </div>
      ) : (
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.subjects.examDateFixedLabel')}
          <Input
            type="date"
            value={examDateFixed}
            onChange={(e) => onChangeExamDateFixed(e.target.value)}
            required
          />
        </label>
      )}
    </>
  )
}

/** 合格基準の種別と、その種別に応じた点数入力欄（素点なら得点と満点、割合なら1つ）。 */
export function SubjectPassingScoreFields({
  value,
  onChange,
}: {
  value: PassingScoreFormState
  onChange: (update: Partial<PassingScoreFormState>) => void
}) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.subjects.passingScoreTypeLabel')}
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={value.type}
          onChange={(e) => onChange({ type: e.target.value as PassingScoreType })}
        >
          {PASSING_SCORE_TYPES.map((option) => (
            <option key={option} value={option}>
              {t(`goals.subjects.passingScoreType.${option}`)}
            </option>
          ))}
        </select>
      </label>
      {value.type === 'RAW_SCORE' ? (
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.subjects.passingScoreRawLabel')}
            <Input
              type="number"
              min={0}
              value={value.rawScoreValue}
              onChange={(e) => onChange({ rawScoreValue: e.target.value })}
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t('goals.subjects.passingScoreMaxLabel')}
            <Input
              type="number"
              min={0}
              value={value.rawMaxValue}
              onChange={(e) => onChange({ rawMaxValue: e.target.value })}
            />
          </label>
        </div>
      ) : (
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.subjects.passingScoreLabel')}
          <Input
            type="number"
            min={0}
            max={100}
            value={value.percentValue}
            onChange={(e) => onChange({ percentValue: e.target.value })}
          />
        </label>
      )}
    </>
  )
}

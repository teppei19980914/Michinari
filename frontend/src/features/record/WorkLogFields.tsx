import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import type { WorkAssignmentRead } from '../../api/goals'
import { PreviousEntryHint } from './PreviousEntryHint'
import { usePreviousWorkLogEntry } from './usePreviousEntryQueries'
import { getWorkLogQuestions, type WorkLogFormValue } from './workLogForm'

type WorkLogFieldsProps = {
  /** 「前回はこう書いていました」ヒントの取得に使う対象日。 */
  targetDate: string
  workAssignments: WorkAssignmentRead[]
  values: Record<number, WorkLogFormValue>
  onChangeField: (
    workAssignmentId: number,
    field: keyof WorkLogFormValue,
    value: string | string[],
  ) => void
}

/** 業務記録入力欄（案件別の自由記述。数値実績は必須としない）。SC-06の仕事用実績入力
 * （仕様書6.5「仕事目標の実績入力」、要件定義書R-75）。ReadingLogFieldsと対になる。
 * 資格試験・読書と異なり日次ノルマ・時間枠を持たないため、案件名のみ表示する。 */
export function WorkLogFields({ targetDate, workAssignments, values, onChangeField }: WorkLogFieldsProps) {
  if (workAssignments.length === 0) {
    return null
  }
  const questions = getWorkLogQuestions()

  return (
    <div className="flex flex-col gap-3">
      {workAssignments.map((workAssignment) => {
        const value = values[workAssignment.id]
        if (!value) {
          return null
        }
        return (
          <WorkLogFieldsCard
            key={workAssignment.id}
            targetDate={targetDate}
            workAssignment={workAssignment}
            questions={questions}
            value={value}
            onChangeField={onChangeField}
          />
        )
      })}
    </div>
  )
}

/** 1案件分のカード。前回ヒントの取得はWorkAssignmentの数だけ呼び出す必要があるため、
 * フックのルール上ループの外へ切り出す（DiaryFields.DiaryFieldsCardと同じ方針）。 */
function WorkLogFieldsCard({
  targetDate,
  workAssignment,
  questions,
  value,
  onChangeField,
}: {
  targetDate: string
  workAssignment: WorkAssignmentRead
  questions: string[]
  value: WorkLogFormValue
  onChangeField: WorkLogFieldsProps['onChangeField']
}) {
  const previousEntry = usePreviousWorkLogEntry(targetDate, workAssignment.id)

  return (
    <Card>
      <p className="font-medium text-gray-900">
        {workAssignment.client_name ?? t('dailyReport.workLog.noClientName')}
      </p>
      <div className="mt-2">
        <PreviousEntryHint entry={previousEntry.data} />
      </div>
      {questions.map((question, index) => (
        <label key={index} className="mt-2 flex flex-col gap-1 text-xs text-gray-600">
          {question}
          <Textarea
            rows={2}
            placeholder={t('dailyReport.questionAnswerPlaceholder')}
            value={value.questionAnswers[index] ?? ''}
            onChange={(e) => {
              const next = [...value.questionAnswers]
              next[index] = e.target.value
              onChangeField(workAssignment.id, 'questionAnswers', next)
            }}
          />
        </label>
      ))}
      <p className="mt-2 text-xs text-gray-400">{t('dailyReport.voiceInputHint')}</p>
      <label className="mt-2 flex flex-col gap-1 text-xs text-gray-600">
        {t('dailyReport.workLog.bodyLabel')}
        <Textarea
          rows={4}
          placeholder={t('dailyReport.workLog.bodyPlaceholder')}
          value={value.freeText}
          onChange={(e) => onChangeField(workAssignment.id, 'freeText', e.target.value)}
        />
      </label>
    </Card>
  )
}

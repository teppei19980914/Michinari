import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import type { GoalRead } from '../../api/goals'
import { PreviousEntryHint } from './PreviousEntryHint'
import { usePreviousDiaryEntry } from './usePreviousEntryQueries'
import { getDiaryQuestions, type DiaryFormValue } from './diaryForm'

type DiaryFieldsProps = {
  /** 「前回はこう書いていました」ヒントの取得に使う対象日。 */
  targetDate: string
  activeGoals: GoalRead[]
  values: Record<number, DiaryFormValue>
  onChangeField: (goalId: number, field: keyof DiaryFormValue, value: string | string[]) => void
}

/** 日記記述欄（仕様書6.5「本日の行動・所感」「本日学んだこと」）。複数目標が同時進行して
 * いる場合は目標ごとに入力欄を分ける（未決事項L-04）。対象は現在ACTIVEな全目標とし、
 * ノルマの有無に関わらず表示する（先行着手した内容を自由記述できる逃げ道を維持する）。 */
export function DiaryFields({ targetDate, activeGoals, values, onChangeField }: DiaryFieldsProps) {
  const showGoalHeading = activeGoals.length > 1
  const questions = getDiaryQuestions()

  return (
    <div className="flex flex-col gap-3">
      {activeGoals.map((goal) => {
        const value = values[goal.id]
        if (!value) {
          return null
        }
        return (
          <DiaryFieldsCard
            key={goal.id}
            targetDate={targetDate}
            goal={goal}
            showGoalHeading={showGoalHeading}
            questions={questions}
            value={value}
            onChangeField={onChangeField}
          />
        )
      })}
    </div>
  )
}

/** 1目標分のカード。前回ヒントの取得（usePreviousDiaryEntry）はActiveGoalの数だけ
 * 呼び出す必要があるため、フックのルール上ループの外へ切り出す。 */
function DiaryFieldsCard({
  targetDate,
  goal,
  showGoalHeading,
  questions,
  value,
  onChangeField,
}: {
  targetDate: string
  goal: GoalRead
  showGoalHeading: boolean
  questions: string[]
  value: DiaryFormValue
  onChangeField: (goalId: number, field: keyof DiaryFormValue, value: string | string[]) => void
}) {
  const previousEntry = usePreviousDiaryEntry(targetDate, goal.id)

  return (
    <Card className="flex flex-col gap-3">
      {showGoalHeading && <h3 className="font-medium text-gray-900">{goal.name}</h3>}
      <PreviousEntryHint entry={previousEntry.data} />
      {questions.map((question, index) => (
        <label key={index} className="flex flex-col gap-1 text-sm text-gray-700">
          {question}
          <Textarea
            rows={2}
            placeholder={t('dailyReport.questionAnswerPlaceholder')}
            value={value.questionAnswers[index] ?? ''}
            onChange={(e) => {
              const next = [...value.questionAnswers]
              next[index] = e.target.value
              onChangeField(goal.id, 'questionAnswers', next)
            }}
          />
        </label>
      ))}
      <p className="text-xs text-gray-400">{t('dailyReport.voiceInputHint')}</p>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('dailyReport.diary.bodyLabel')}
        <Textarea
          rows={4}
          value={value.freeText}
          onChange={(e) => onChangeField(goal.id, 'freeText', e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('dailyReport.diary.learnedLabel')}
        <Textarea
          rows={4}
          placeholder={t('dailyReport.diary.learnedPlaceholder')}
          value={value.diaryLearned}
          onChange={(e) => onChangeField(goal.id, 'diaryLearned', e.target.value)}
        />
      </label>
    </Card>
  )
}

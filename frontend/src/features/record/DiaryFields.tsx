import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import type { GoalRead } from '../../api/goals'
import { PreviousEntryHint } from './PreviousEntryHint'
import { usePreviousDiaryEntry } from './usePreviousEntryQueries'
import type { DiaryFormValue } from './diaryForm'

type DiaryFieldsProps = {
  /** 「前回はこう書いていました」ヒントの取得に使う対象日。 */
  targetDate: string
  activeGoals: GoalRead[]
  values: Record<number, DiaryFormValue>
  onChangeLearned: (goalId: number, value: string) => void
}

/** 日記記述欄（資格試験）。入力は「学んだこと・理解したこと」1つに集約し、利用者が入力先に
 * 迷わないようにする。複数目標が同時進行している場合は目標ごとに入力欄を分ける（未決事項L-04）。 */
export function DiaryFields({ targetDate, activeGoals, values, onChangeLearned }: DiaryFieldsProps) {
  const showGoalHeading = activeGoals.length > 1

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
            value={value}
            onChangeLearned={onChangeLearned}
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
  value,
  onChangeLearned,
}: {
  targetDate: string
  goal: GoalRead
  showGoalHeading: boolean
  value: DiaryFormValue
  onChangeLearned: (goalId: number, value: string) => void
}) {
  const previousEntry = usePreviousDiaryEntry(targetDate, goal.id)

  return (
    <Card className="flex flex-col gap-3">
      {showGoalHeading && <h3 className="font-medium text-text-primary">{goal.name}</h3>}
      <PreviousEntryHint entry={previousEntry.data} />
      {value.diaryBody !== '' && (
        <div className="flex flex-col gap-1 rounded-md bg-surface-muted p-2 text-sm text-text-secondary">
          <p className="text-xs text-text-disabled">{t('dailyReport.diary.bodyLabel')}</p>
          <p className="whitespace-pre-wrap">{value.diaryBody}</p>
        </div>
      )}
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        {t('dailyReport.diary.learnedLabel')}
        <Textarea
          rows={5}
          placeholder={t('dailyReport.diary.learnedPlaceholder')}
          value={value.diaryLearned}
          onChange={(e) => onChangeLearned(goal.id, e.target.value)}
        />
      </label>
      <p className="text-xs text-text-disabled">{t('dailyReport.voiceInputHint')}</p>
    </Card>
  )
}

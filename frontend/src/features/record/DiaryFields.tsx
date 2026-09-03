import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import type { GoalRead } from '../../api/goals'
import type { DiaryFormValue } from './diaryForm'

type DiaryFieldsProps = {
  activeGoals: GoalRead[]
  values: Record<number, DiaryFormValue>
  onChangeField: (goalId: number, field: keyof DiaryFormValue, value: string) => void
}

/** 日記記述欄（仕様書6.5「本日の行動・所感」「本日学んだこと」）。複数目標が同時進行して
 * いる場合は目標ごとに入力欄を分ける（未決事項L-04）。対象は現在ACTIVEな全目標とし、
 * ノルマの有無に関わらず表示する（先行着手した内容を自由記述できる逃げ道を維持する）。 */
export function DiaryFields({ activeGoals, values, onChangeField }: DiaryFieldsProps) {
  const showGoalHeading = activeGoals.length > 1

  return (
    <div className="flex flex-col gap-3">
      {activeGoals.map((goal) => {
        const value = values[goal.id]
        if (!value) {
          return null
        }
        return (
          <Card key={goal.id} className="flex flex-col gap-3">
            {showGoalHeading && (
              <h3 className="font-medium text-gray-900">{goal.name}</h3>
            )}
            <label className="flex flex-col gap-1 text-sm text-gray-700">
              {t('dailyReport.diary.bodyLabel')}
              <Textarea
                rows={4}
                value={value.diaryBody}
                onChange={(e) => onChangeField(goal.id, 'diaryBody', e.target.value)}
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
      })}
    </div>
  )
}

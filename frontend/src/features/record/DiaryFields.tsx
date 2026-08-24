import { t } from '../../locales/t'
import { Textarea } from '../../components/Textarea'

type DiaryFieldsProps = {
  diaryBody: string
  diaryLearned: string
  onChangeDiaryBody: (value: string) => void
  onChangeDiaryLearned: (value: string) => void
}

/** 日記記述欄（仕様書6.5「本日の行動・所感」「本日学んだこと」）。 */
export function DiaryFields({
  diaryBody,
  diaryLearned,
  onChangeDiaryBody,
  onChangeDiaryLearned,
}: DiaryFieldsProps) {
  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('dailyReport.diary.bodyLabel')}
        <Textarea
          rows={4}
          value={diaryBody}
          onChange={(e) => onChangeDiaryBody(e.target.value)}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('dailyReport.diary.learnedLabel')}
        <Textarea
          rows={4}
          placeholder={t('dailyReport.diary.learnedPlaceholder')}
          value={diaryLearned}
          onChange={(e) => onChangeDiaryLearned(e.target.value)}
        />
      </label>
    </div>
  )
}

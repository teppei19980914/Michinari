import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { components } from '../../types/api.d.ts'

type DiaryEntryRead = components['schemas']['DiaryEntryRead']

/** 日記（目標別）の読み取り専用表示（SC-08 日次報告閲覧、および確定済みの資格勉強タブ、
 * 仕様書6.7）。本文・学んだことの両方が空のエントリは呼び出し側で除外しておくこと。 */
export function DiaryEntrySummaryList({ diaryEntries }: { diaryEntries: DiaryEntryRead[] }) {
  if (diaryEntries.length === 0) {
    return null
  }

  return (
    <Card className="flex flex-col gap-4">
      <h2 className="font-medium text-gray-900">{t('dailyReportView.diary.title')}</h2>
      {diaryEntries.map((entry, index) => (
        <div key={entry.goal_id ?? index} className="flex flex-col gap-3">
          {diaryEntries.length > 1 && entry.goal_name && (
            <h3 className="font-medium text-gray-900">{entry.goal_name}</h3>
          )}
          {entry.diary_body && (
            <div>
              <p className="text-xs text-gray-400">{t('dailyReport.diary.bodyLabel')}</p>
              <p className="whitespace-pre-wrap text-sm text-gray-900">{entry.diary_body}</p>
            </div>
          )}
          {entry.diary_learned && (
            <div>
              <p className="text-xs text-gray-400">{t('dailyReport.diary.learnedLabel')}</p>
              <p className="whitespace-pre-wrap text-sm text-gray-900">{entry.diary_learned}</p>
            </div>
          )}
        </div>
      ))}
    </Card>
  )
}

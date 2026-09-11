import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { ReadingLogRead } from '../../api/records'

export type BookLabel = { title: string }

/** 想起記録の読み取り専用表示（SC-08 日次報告閲覧、StudyLogSummaryListの読書版）。
 * 書名はGoalDetailRead.book経由で取得したものをbookLabels経由で受け取る。 */
export function ReadingLogSummaryList({
  readingLogs,
  bookLabels,
}: {
  readingLogs: ReadingLogRead[]
  bookLabels: Map<number, BookLabel>
}) {
  if (readingLogs.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-2">
      {readingLogs.map((log) => {
        const label = bookLabels.get(log.book_id)
        return (
          <Card key={log.id}>
            <p className="font-medium text-gray-900">
              {label?.title ?? t('dailyReportView.readingLog.unknownBook', { id: log.book_id })}
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-gray-900">{log.recall_body}</p>
            {log.current_page !== null && (
              <dl className="mt-2 text-sm text-gray-600">
                <dt className="text-gray-400">{t('dailyReportView.readingLog.currentPage')}</dt>
                <dd>{log.current_page}</dd>
              </dl>
            )}
          </Card>
        )
      })}
    </div>
  )
}

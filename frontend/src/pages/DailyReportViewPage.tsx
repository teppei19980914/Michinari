import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { Card } from '../components/Card'
import { getQuota, getRecord } from '../api/records'
import { StudyLogSummaryList, type MaterialLabel } from '../features/record/StudyLogSummaryList'
import { ChatPanel } from '../features/record/ChatPanel'
import { CommentSection } from '../features/record/CommentSection'

/** SC-08 日次報告閲覧（仕様書6.7）。実績・日記は読み取り専用、コメントのみ追加・修正・削除
 * が可能。カレンダーから「進捗のみ登録済かつ2日以上前」を選んだ場合もこの画面を再利用する
 * （日記・対話はデータが無ければ自然に非表示になるため、報告済/進捗のみのどちらにも対応する）。
 * コメント機能（CommentSection）は進捗のみ登録済の記録にも表示する。仕様書6.7はコメントを
 * 報告済（SC-08）の文脈で説明しているが、record_stateによらずコメント可否を区別する記載は
 * なく、バックエンドのadd_comment（record_service.py）もrecord_stateを問わず許可している
 * ため、この画面を開けるあらゆる記録に対して一貫して提供する。 */
export function DailyReportViewPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string

  const recordQuery = useQuery({
    queryKey: ['record', targetDate],
    queryFn: () => getRecord(targetDate),
  })
  const quotaQuery = useQuery({
    queryKey: ['quota', targetDate],
    queryFn: () => getQuota(targetDate),
  })

  if (recordQuery.isLoading || quotaQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (recordQuery.isError || !recordQuery.data) {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(recordQuery.error)}</p>
  }

  const record = recordQuery.data
  const materialLabels = new Map<number, MaterialLabel>(
    (quotaQuery.data ?? []).map((item) => [
      item.material_id,
      { name: item.material_name, unitLabel: item.unit_label },
    ]),
  )

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">
        {t('dailyReportView.title', { date: targetDate })}
      </h1>

      <section className="flex flex-col gap-2">
        <h2 className="font-medium text-gray-900">{t('dailyReportView.studyLog.title')}</h2>
        <StudyLogSummaryList studyLogs={record.study_logs} materialLabels={materialLabels} />
      </section>

      {(record.diary_body || record.diary_learned) && (
        <Card className="flex flex-col gap-3">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.diary.title')}</h2>
          {record.diary_body && (
            <div>
              <p className="text-xs text-gray-400">{t('dailyReport.diary.bodyLabel')}</p>
              <p className="whitespace-pre-wrap text-sm text-gray-900">{record.diary_body}</p>
            </div>
          )}
          {record.diary_learned && (
            <div>
              <p className="text-xs text-gray-400">{t('dailyReport.diary.learnedLabel')}</p>
              <p className="whitespace-pre-wrap text-sm text-gray-900">{record.diary_learned}</p>
            </div>
          )}
        </Card>
      )}

      {record.chat_messages.length > 0 && (
        <Card className="flex flex-col gap-2">
          <h2 className="font-medium text-gray-900">{t('dailyReportView.chatHistory.title')}</h2>
          <ChatPanel messages={record.chat_messages} readOnly />
        </Card>
      )}

      <CommentSection targetDate={targetDate} comments={record.comments} />
    </div>
  )
}

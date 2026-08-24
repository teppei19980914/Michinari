import { useQuery } from '@tanstack/react-query'
import { getDailyMessage } from '../../api/records'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'

/**
 * 今日の一言（仕様書6.1「AIが生成した肯定的な短文。生成日が当日でない場合のみ再生成」）。
 * 生成に時間がかかる場合があるため、他の要素とは独立したクエリで非同期・遅延表示する
 * （Phase6完了条件）。
 */
export function TodayMessage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['daily-message'],
    queryFn: getDailyMessage,
  })

  if (isError) {
    return null
  }

  return (
    <Card className="bg-blue-50">
      {isLoading || !data ? (
        <p className="text-sm text-gray-500">{t('dashboard.todayMessage.loading')}</p>
      ) : (
        <p className="text-sm text-gray-800">{data.body}</p>
      )}
    </Card>
  )
}

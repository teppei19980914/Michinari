import { useQuery } from '@tanstack/react-query'
import { getDailyMessage } from '../../api/records'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'

/**
 * 今日の一言（仕様書6.1「AIが生成した肯定的な短文。生成日が当日でない場合のみ再生成」）。
 * 生成に時間がかかる場合があるため、他の要素とは独立したクエリで非同期・遅延表示する
 * （Phase6完了条件）。複数目標が同時進行している場合は目標ごとに独立して生成される
 * （未決事項L-04）。2件以上のときのみ目標名見出しで区別する（1目標のみ・目標非依存の
 * 1件のみのときは既存の見た目のまま）。
 */
export function TodayMessage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['daily-message'],
    queryFn: getDailyMessage,
  })

  if (isError) {
    return null
  }

  const showGoalHeading = (data?.length ?? 0) > 1

  return (
    <Card className="bg-blue-50">
      {isLoading || !data ? (
        <p className="text-sm text-gray-500">{t('dashboard.todayMessage.loading')}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {data.map((message, index) => (
            <div key={message.goal_id ?? index}>
              {showGoalHeading && message.goal_name && (
                <p className="text-xs font-medium text-gray-600">{message.goal_name}</p>
              )}
              <p className="text-sm text-gray-800">{message.body}</p>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

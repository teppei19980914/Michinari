import { useQuery } from '@tanstack/react-query'
import { getDailyMessage } from '../../api/records'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'

type TodayMessageProps = {
  /** 表示対象のgoal_id（GoalTabBarの選択目標、Phase25）。nullのときは
   * 目標非依存のメッセージ（着手中の目標が0件の場合のフォールバック）のみ表示する。 */
  goalId: number | null
}

/**
 * 今日の一言（仕様書6.1「AIが生成した肯定的な短文。生成日が当日でない場合のみ再生成」）。
 * 生成に時間がかかる場合があるため、他の要素とは独立したクエリで非同期・遅延表示する
 * （Phase6完了条件）。複数目標が同時進行している場合は目標ごとに独立して生成されるため、
 * GoalTabBarで選択中の目標分のみ表示する（Phase25、旧仕様は複数目標分を1画面に列挙していた）。
 */
export function TodayMessage({ goalId }: TodayMessageProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['daily-message'],
    queryFn: getDailyMessage,
  })

  if (isError) {
    return null
  }

  const messages = data?.filter((message) => message.goal_id === goalId) ?? []

  if (!isLoading && messages.length === 0) {
    return null
  }

  return (
    <Card className="bg-blue-50">
      {isLoading ? (
        <p className="text-sm text-gray-500">{t('dashboard.todayMessage.loading')}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {messages.map((message, index) => (
            <div key={message.goal_id ?? index}>
              <p className="text-sm text-gray-800">{message.body}</p>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

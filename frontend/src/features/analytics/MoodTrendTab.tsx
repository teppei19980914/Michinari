import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getMoodAnalytics } from '../../api/analytics'
import { QUERY_KEYS } from '../../constants/queryKeys'

type MoodTrendTabProps = { goalId: number }

/** 分析画面「気分の推移」タブ（開発Todo「ひとこと記録」v1.0 要件5、仕様書6.8）。
 * 気分は目標ではなくカテゴリ（EXAM/READING/WORK）に紐づくため、同カテゴリの別目標でも
 * 同じ推移が表示される（api/analytics.getMoodAnalyticsのdocstring参照）。 */
export function MoodTrendTab({ goalId }: MoodTrendTabProps) {
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsMood(goalId),
    queryFn: () => getMoodAnalytics(goalId),
  })

  if (query.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-danger-text">{apiErrorMessage(query.error)}</p>
  }
  if (query.data.length === 0) {
    return <p className="text-sm text-text-faint">{t('analytics.mood.empty')}</p>
  }

  return (
    <Card>
      <h3 className="font-medium text-text-primary">{t('analytics.mood.trendTitle')}</h3>
      <ul className="mt-2 flex flex-col gap-1">
        {query.data.map((point) => (
          <li key={point.record_date} className="flex items-baseline justify-between gap-2 text-sm">
            <span className="text-text-secondary">{point.record_date}</span>
            <span className="text-text-primary">
              {t(`dailyReport.quickRecord.moodStamps.${point.mood_value}`)}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

import { useQuery } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { apiErrorMessage } from '../../api/client'
import { getQuizAccuracyAnalytics } from '../../api/analytics'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { formatAccuracyPercent } from './quizAccuracyFormat'

type QuizAccuracyTabProps = { goalId: number }

/** 分析画面「クイズ正答率」タブ（開発Todo_復習クイズ_v1.0、仕様書6.8）。資格試験・読書の
 * 目標のみ対象。正答率は分子・分母から都度算出する（保存値を使わない）。 */
export function QuizAccuracyTab({ goalId }: QuizAccuracyTabProps) {
  const query = useQuery({
    queryKey: QUERY_KEYS.analyticsQuizAccuracy(goalId),
    queryFn: () => getQuizAccuracyAnalytics(goalId),
  })

  if (query.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (query.isError || !query.data) {
    return <p className="text-sm text-danger-text">{apiErrorMessage(query.error)}</p>
  }
  if (query.data.trend.length === 0) {
    return <p className="text-sm text-text-faint">{t('analytics.quizAccuracy.empty')}</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h3 className="font-medium text-text-primary">{t('analytics.quizAccuracy.trendTitle')}</h3>
        <ul className="mt-2 flex flex-col gap-1">
          {query.data.trend.map((point) => (
            <li
              key={point.period_start}
              className="flex items-baseline justify-between gap-2 text-sm"
            >
              <span className="text-text-secondary">
                {t('analytics.quizAccuracy.weekRangeLabel', {
                  start: point.period_start,
                  end: point.period_end,
                })}
              </span>
              <span className="text-text-primary">
                {formatAccuracyPercent(point.correct_count, point.answer_count)}
                {t('analytics.quizAccuracy.fractionLabel', {
                  correct: point.correct_count,
                  total: point.answer_count,
                })}
              </span>
            </li>
          ))}
        </ul>
      </Card>
      {query.data.weak_themes.length > 0 && (
        <Card>
          <h3 className="font-medium text-text-primary">
            {t('analytics.quizAccuracy.weakThemesTitle')}
          </h3>
          <ul className="mt-2 flex flex-col gap-1">
            {query.data.weak_themes.map((theme) => (
              <li
                key={theme.theme_id}
                className="flex items-baseline justify-between gap-2 text-sm"
              >
                <span className="text-text-secondary">{theme.theme_name}</span>
                <span className="text-text-primary">
                  {formatAccuracyPercent(theme.correct_count, theme.answer_count)}
                  {t('analytics.quizAccuracy.fractionLabel', {
                    correct: theme.correct_count,
                    total: theme.answer_count,
                  })}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

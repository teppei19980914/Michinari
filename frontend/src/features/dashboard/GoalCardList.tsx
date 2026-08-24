import { Link } from 'react-router-dom'
import { ROUTES } from '../../constants/routes'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { formatPercent } from '../../utils/format'
import type { DashboardRead } from '../../api/dashboard'

function formatProgressRate(rate: number | null): string {
  return rate === null ? t('dashboard.goalCard.notAvailable') : formatPercent(rate)
}

function formatRemainingDays(days: number | null): string {
  return days === null
    ? t('dashboard.goalCard.remainingDaysUnavailable')
    : t('dashboard.goalCard.remainingDays', { days })
}

function formatForecastDeviation(days: number | null): string {
  return days === null
    ? t('dashboard.goalCard.forecastDeviationUnavailable')
    : t('dashboard.goalCard.forecastDeviation', { days: Math.round(days) })
}

/** 目標カード一覧（仕様書6.1「進行中の各目標について、全体進捗率、残日数、
 * 完了予測日との乖離を表示」）。 */
export function GoalCardList({ goalCards }: { goalCards: DashboardRead['goal_cards'] }) {
  if (goalCards.length === 0) {
    return null
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {goalCards.map((goal) => (
        <Link key={goal.goal_id} to={ROUTES.goalDetail(goal.goal_id)}>
          <Card className="h-full hover:border-blue-300">
            <h3 className="mb-2 font-medium text-gray-900">{goal.goal_name}</h3>
            <dl className="space-y-1 text-sm text-gray-600">
              <div className="flex justify-between">
                <dt>{t('dashboard.goalCard.progressRate')}</dt>
                <dd>{formatProgressRate(goal.progress_rate)}</dd>
              </div>
              <div>{formatRemainingDays(goal.remaining_days)}</div>
              <div>{formatForecastDeviation(goal.forecast_deviation_days)}</div>
            </dl>
          </Card>
        </Link>
      ))}
    </div>
  )
}

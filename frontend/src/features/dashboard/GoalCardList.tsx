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

function formatRemainingDaysReading(days: number | null): string {
  return days === null
    ? t('dashboard.goalCard.remainingDaysUnavailable')
    : t('dashboard.goalCard.remainingDaysReading', { days })
}

function formatForecastDeviation(days: number | null): string {
  return days === null
    ? t('dashboard.goalCard.forecastDeviationUnavailable')
    : t('dashboard.goalCard.forecastDeviation', { days: Math.round(days) })
}

type GoalCard = DashboardRead['goal_cards'][number]

/** 読書目標のカード内容（仕様書6.1、要件定義書R-63「ノルマではなく残日数・直近記録日・
 * 連続記録日数」）。完了予測日との乖離は表示しない（EXAM専用の計画管理のため）。 */
function ReadingGoalCard({ goal }: { goal: GoalCard }) {
  const book = goal.book
  return (
    <>
      <h3 className="mb-2 font-medium text-gray-900">{goal.goal_name}</h3>
      <dl className="space-y-1 text-sm text-gray-600">
        <div>{formatRemainingDaysReading(goal.remaining_days)}</div>
        {book && (
          <>
            <div>
              {book.last_reading_date
                ? t('dashboard.goalCard.lastReadingDate', { date: book.last_reading_date })
                : t('dashboard.goalCard.lastReadingDateUnavailable')}
            </div>
            <div>
              {t('dashboard.goalCard.currentStreak', { days: book.current_streak })}
            </div>
            {book.progress_rate !== null && (
              <div className="flex justify-between">
                <dt>{t('dashboard.goalCard.pageProgress')}</dt>
                <dd>{formatProgressRate(book.progress_rate)}</dd>
              </div>
            )}
          </>
        )}
      </dl>
    </>
  )
}

function ExamGoalCard({ goal }: { goal: GoalCard }) {
  return (
    <>
      <h3 className="mb-2 font-medium text-gray-900">{goal.goal_name}</h3>
      <dl className="space-y-1 text-sm text-gray-600">
        <div className="flex justify-between">
          <dt>{t('dashboard.goalCard.progressRate')}</dt>
          <dd>{formatProgressRate(goal.progress_rate)}</dd>
        </div>
        <div>{formatRemainingDays(goal.remaining_days)}</div>
        <div>{formatForecastDeviation(goal.forecast_deviation_days)}</div>
      </dl>
    </>
  )
}

/** 目標カード一覧（仕様書6.1「進行中の各目標について、全体進捗率、残日数、
 * 完了予測日との乖離を表示」）。読書目標（category=READING）はDSH-06に従い、
 * ノルマ相当の指標ではなく残日数・直近記録日・連続記録日数を表示する。 */
export function GoalCardList({ goalCards }: { goalCards: DashboardRead['goal_cards'] }) {
  if (goalCards.length === 0) {
    return null
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {goalCards.map((goal) => (
        <Link key={goal.goal_id} to={ROUTES.goalDetail(goal.goal_id)}>
          <Card className="h-full hover:border-blue-300">
            {goal.category === 'READING' ? (
              <ReadingGoalCard goal={goal} />
            ) : (
              <ExamGoalCard goal={goal} />
            )}
          </Card>
        </Link>
      ))}
    </div>
  )
}

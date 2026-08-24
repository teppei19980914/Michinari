import { Link } from 'react-router-dom'
import { ROUTES } from '../../constants/routes'
import { t } from '../../locales/t'
import type { DashboardRead } from '../../api/dashboard'

type WarningBannerProps = {
  goalCards: DashboardRead['goal_cards']
}

/**
 * 警告バナー（仕様書6.1「警告または強制リプラン条件を満たす目標がある場合に表示」）。
 * 該当目標が無ければ何も描画しない。
 */
export function WarningBanner({ goalCards }: WarningBannerProps) {
  const targets = goalCards.filter((goal) => goal.has_warning || goal.has_forced_replan)
  if (targets.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-2">
      {targets.map((goal) => (
        <Link
          key={goal.goal_id}
          to={ROUTES.goalDetail(goal.goal_id)}
          className="block rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 hover:bg-amber-100"
        >
          <span className="font-medium">{goal.goal_name}</span>：
          {goal.has_forced_replan ? t('dashboard.warningBanner.forcedReplan') : t('dashboard.warningBanner.warning')}
        </Link>
      ))}
    </div>
  )
}

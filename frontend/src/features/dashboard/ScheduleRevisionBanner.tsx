import { Link } from 'react-router-dom'
import { ROUTES } from '../../constants/routes'
import { t } from '../../locales/t'
import type { DashboardRead } from '../../api/dashboard'

type ScheduleRevisionBannerProps = {
  goalCards: DashboardRead['goal_cards']
}

/**
 * スケジュールの修正案の案内（開発Todo_スケジュール・ガントチャート_v1.1 13.8、単位5）。
 * 未判断の修正案がある目標へ、スケジュールタブへのリンクを添えて案内する。
 * 該当目標が無ければ何も描画しない（`WarningBanner`と同じ方針）。
 */
export function ScheduleRevisionBanner({ goalCards }: ScheduleRevisionBannerProps) {
  const targets = goalCards.filter((goal) => goal.has_pending_schedule_revision)
  if (targets.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-2">
      {targets.map((goal) => (
        <Link
          key={goal.goal_id}
          to={ROUTES.goalScheduleTab(goal.goal_id)}
          className="block rounded-md border border-accent bg-surface-muted px-4 py-3 text-sm text-text-primary hover:bg-surface"
        >
          <span className="font-medium">{goal.goal_name}</span>：
          {t('dashboard.scheduleRevisionBanner.message')}
        </Link>
      ))}
    </div>
  )
}

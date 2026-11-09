import { Link } from 'react-router-dom'
import { format, parseISO } from 'date-fns'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { ROUTES } from '../../constants/routes'
import type { DashboardRead } from '../../api/dashboard'
import { resolveOnThisDayPeriodLabel } from './onThisDayLabel'

type OnThisDaySectionProps = {
  /** 目標に紐づかないアプリ全体の値（開発Todo_1年前の今日_v1.0 §0 V8）。表示しない日・
   * 候補が無い日はnull。 */
  onThisDay: DashboardRead['on_this_day']
}

/** 1年前の今日（開発Todo_1年前の今日_v1.0）。過去の同じ日の記録をときどき紹介する。
 * クリックでその日の日次報告閲覧画面（SC-08）へ遷移する（既存のRoadmapDiagram・
 * GoalConsultationAnswer・Calendarと同じ既存ルートをそのまま使う）。 */
export function OnThisDaySection({ onThisDay }: OnThisDaySectionProps) {
  if (onThisDay === null) {
    return null
  }

  return (
    <Link to={ROUTES.dailyReportView(onThisDay.record_date)} className="block">
      <Card className="hover:bg-accent-muted-bg">
        <div className="flex items-baseline justify-between">
          <h2 className="font-medium text-text-primary">{t('dashboard.onThisDay.title')}</h2>
          <span className="text-xs text-text-faint">
            {format(parseISO(onThisDay.record_date), 'M/d')}
          </span>
        </div>
        <p className="mt-1 text-sm text-text-faint">
          {t('dashboard.onThisDay.goalLabel', {
            goalName: onThisDay.goal_name,
            periodLabel: resolveOnThisDayPeriodLabel(onThisDay.months_ago),
          })}
        </p>
        <p className="mt-1 text-sm text-text-primary">{onThisDay.excerpt}</p>
      </Card>
    </Link>
  )
}

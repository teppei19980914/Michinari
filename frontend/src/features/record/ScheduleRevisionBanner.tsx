import { Link } from 'react-router-dom'
import { ROUTES } from '../../constants/routes'
import { t } from '../../locales/t'
import type { ScheduleRevisionBannerStatus } from './useScheduleRevisionBanner'

/**
 * 日次報告の確定後の案内（開発Todo_スケジュール・ガントチャート_v1.1 13.1・13.8、単位5）。
 * `status`が無い（生成の対象外）・`no_proposal`（修正が必要な行が無かった）のときは
 * 何も表示しない。
 */
export function ScheduleRevisionBanner({
  goalId,
  status,
}: {
  goalId: number
  status: ScheduleRevisionBannerStatus | undefined
}) {
  if (status === undefined || status === 'no_proposal') {
    return null
  }
  if (status === 'generating') {
    return (
      <p className="text-xs text-text-muted">{t('dailyReport.scheduleRevision.generating')}</p>
    )
  }
  if (status === 'failed') {
    return (
      <p className="text-xs text-danger-text">{t('dailyReport.scheduleRevision.failed')}</p>
    )
  }
  return (
    <Link to={ROUTES.goalScheduleTab(goalId)} className="block text-xs text-accent underline">
      {t('dailyReport.scheduleRevision.succeeded')}
    </Link>
  )
}

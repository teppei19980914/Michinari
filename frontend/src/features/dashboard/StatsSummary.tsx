import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { formatPercent } from '../../utils/format'
import type { DashboardRead } from '../../api/dashboard'

type StatsSummaryProps = {
  goalStats: DashboardRead['goal_stats']
  reportRateWindowDays: number
}

/** 統計サマリ（仕様書6.1「連続報告日数、直近30日の報告率、バッファ消費率、実効速度」）。
 * 連続報告日数・報告率・バッファ消費率は目標開始日を起点に算出するため、目標ごとに表示する。
 * 「直近N日」のNは app_setting（dashboard.report_rate_window_days）から取得した値を表示し、
 * ソースコードへ数値を直接書かない（CLAUDE.md ゼロハードコーディング）。 */
export function StatsSummary({ goalStats, reportRateWindowDays }: StatsSummaryProps) {
  if (goalStats.length === 0) {
    return null
  }

  return (
    <Card>
      <h2 className="mb-2 font-medium text-gray-900">{t('dashboard.stats.title')}</h2>
      <div className="space-y-4">
        {goalStats.map((stats) => (
          <div key={stats.goal_id}>
            <h3 className="text-sm font-medium text-gray-700">{stats.goal_name}</h3>
            <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-600 sm:grid-cols-3">
              <div className="flex justify-between">
                <dt>{t('dashboard.stats.consecutiveReportDays')}</dt>
                <dd>{stats.consecutive_report_days}</dd>
              </div>
              <div className="flex justify-between">
                <dt>{t('dashboard.stats.recentReportRate', { windowDays: reportRateWindowDays })}</dt>
                <dd>{formatPercent(stats.recent_report_rate)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>{t('dashboard.stats.bufferUsageRate')}</dt>
                <dd>
                  {stats.buffer_usage_rate === null
                    ? t('dashboard.stats.bufferUsageRateUnavailable')
                    : formatPercent(stats.buffer_usage_rate)}
                </dd>
              </div>
            </dl>
            {stats.material_speeds.length > 0 && (
              <ul className="mt-1 text-xs text-gray-500">
                {stats.material_speeds.map((entry) => (
                  <li key={entry.material_id}>
                    {t('dashboard.stats.effectiveSpeed')}（{entry.material_name}）：
                    {entry.speed === null
                      ? t('dashboard.stats.effectiveSpeedUnavailable')
                      : `${entry.speed.toFixed(2)}${entry.unit_label}${t('dashboard.stats.perHour')}`}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}

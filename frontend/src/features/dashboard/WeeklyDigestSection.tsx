import { format, parseISO } from 'date-fns'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { DashboardRead } from '../../api/dashboard'
import { resolveWeeklyDigestDisplay } from './resolveWeeklyDigestDisplay'

type WeeklyDigestSectionProps = {
  /** 選択中の目標分のみ（DashboardPageで絞り込み済み）。着手中の目標が無ければnull。 */
  digest: DashboardRead['weekly_digests'][number] | null
}

/** 先週のまとめ（仕様書6.1「先週のまとめ」、S-4 4-4）。
 *
 * AI週次要約が生成済みならその本文を、無ければ記録日数・投下時間の非AI集計を表示する
 * （AI未設定でも先週の振り返りが得られるようにする）。表示内容の判定は
 * resolveWeeklyDigestDisplay（.ts、CODING_RULES.md「フロントの分岐は.tsへ切り出す」）
 * に委ね、本コンポーネントは描画のみを担う。 */
export function WeeklyDigestSection({ digest }: WeeklyDigestSectionProps) {
  if (digest === null) {
    return null
  }
  const display = resolveWeeklyDigestDisplay(digest)
  const weekRange = `${format(parseISO(digest.week_start_date), 'M/d')}〜${format(parseISO(digest.week_end_date), 'M/d')}`

  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <h2 className="font-medium text-gray-900">{t('dashboard.weeklyDigest.title')}</h2>
        <span className="text-xs text-gray-500">{weekRange}</span>
      </div>
      {display.kind === 'ai_summary' && (
        <p className="mt-1 text-sm text-gray-800">{display.text}</p>
      )}
      {display.kind === 'no_records' && (
        <p className="mt-1 text-sm text-gray-500">{t('dashboard.weeklyDigest.noRecords')}</p>
      )}
      {display.kind === 'record_summary' && (
        <p className="mt-1 text-sm text-gray-800">
          {t('dashboard.weeklyDigest.recordedDays', { days: display.recordedDays })}
          {display.totalMinutes !== null &&
            `　${t('dashboard.weeklyDigest.totalMinutes', { minutes: display.totalMinutes })}`}
        </p>
      )}
    </Card>
  )
}

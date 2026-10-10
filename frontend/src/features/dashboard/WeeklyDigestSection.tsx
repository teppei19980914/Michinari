import { format, parseISO } from 'date-fns'
import { getLocale, t } from '../../locales/t'
import { Card } from '../../components/Card'
import { MarkdownText } from '../../components/MarkdownText'
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
 * に委ね、本コンポーネントは描画のみを担う。
 *
 * AI要約本文はマークダウン形式（見出し・箇条書き・強調等）で生成されるため、MarkdownText
 * （XSS安全設計の詳細もそちらを参照）でプレビュー表示する。 */
export function WeeklyDigestSection({ digest }: WeeklyDigestSectionProps) {
  if (digest === null) {
    return null
  }
  const display = resolveWeeklyDigestDisplay(digest)
  const rangeMarker = getLocale() === 'en' ? '–' : '〜'
  const weekRange = `${format(parseISO(digest.week_start_date), 'M/d')}${rangeMarker}${format(parseISO(digest.week_end_date), 'M/d')}`

  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <h2 className="font-medium text-text-primary">{t('dashboard.weeklyDigest.title')}</h2>
        <span className="text-xs text-text-faint">{weekRange}</span>
      </div>
      {display.kind === 'ai_summary' && (
        <MarkdownText text={display.text} className="mt-1 text-text-primary" />
      )}
      {display.kind === 'no_records' && (
        <p className="mt-1 text-sm text-text-faint">{t('dashboard.weeklyDigest.noRecords')}</p>
      )}
      {display.kind === 'record_summary' && (
        <p className="mt-1 text-sm text-text-primary">
          {t('dashboard.weeklyDigest.recordedDays', {
            days: display.recordedDays,
            count: display.recordedDays,
          })}
          {display.totalMinutes !== null &&
            `${getLocale() === 'en' ? '  ' : '　'}${t('dashboard.weeklyDigest.totalMinutes', {
              minutes: display.totalMinutes,
              count: display.totalMinutes,
            })}`}
        </p>
      )}
    </Card>
  )
}

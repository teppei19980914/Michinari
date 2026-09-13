/** ナレッジエクスポート（SC-13）の学習サマリ。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）への対応で KnowledgeExportPage
 * から移したものである。中身は移設前と同じで、振る舞いは変えていない。
 *
 * 資格試験は計画管理の指標（総学習時間・報告率・リプラン回数・最終到達品質）を、読書・仕事は
 * 記録の継続を示す指標（記録日数・最長連続記録日数）を出す（設計書データ構造編7.1）。
 * サーバの`data`は出力項目選択で含まれるキーが変わるため緩く型付けされており、種別ごとに
 * 形を絞り込んで読む（knowledgeExportSummary.ts）。 */
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import type { KnowledgeExportContentRead } from '../../api/export'
import {
  computeLatestQualityValue,
  type ExportSummary,
  type QualityTrendEntry,
  type ReadingExportSummary,
  type WorkExportSummary,
} from './knowledgeExportSummary'

export function ExportSummaryCard({
  content,
  isReading,
  isWork,
}: {
  content: KnowledgeExportContentRead | undefined
  isReading: boolean
  isWork: boolean
}) {
  if (!content?.data.summary) {
    return null
  }
  if (isReading || isWork) {
    const summary = content.data.summary as ReadingExportSummary | WorkExportSummary
    return (
      <Card className="flex flex-col gap-2">
        <h2 className="font-medium text-gray-900">
          {t(
            isWork
              ? 'knowledgeExport.summary.workTitle'
              : 'knowledgeExport.summary.readingTitle',
          )}
        </h2>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-700">
          <dt className="text-gray-500">{t('knowledgeExport.summary.recordDays')}</dt>
          <dd>{summary.record_days}</dd>
          <dt className="text-gray-500">{t('knowledgeExport.summary.maxStreakDays')}</dt>
          <dd>{summary.max_streak_days}</dd>
        </dl>
      </Card>
    )
  }
  const summary = content.data.summary as ExportSummary
  const qualityTrend = (content.data.quality_trend as QualityTrendEntry[] | undefined) ?? []
  const latestQuality = computeLatestQualityValue(qualityTrend)

  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-gray-900">{t('knowledgeExport.summary.title')}</h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-700">
        <dt className="text-gray-500">{t('knowledgeExport.summary.totalHours')}</dt>
        <dd>{(summary.total_minutes / 60).toFixed(1)}</dd>
        <dt className="text-gray-500">{t('knowledgeExport.summary.studyDays')}</dt>
        <dd>{summary.study_days}</dd>
        <dt className="text-gray-500">{t('knowledgeExport.summary.reportRate')}</dt>
        <dd>{(summary.report_rate * 100).toFixed(0)}%</dd>
        <dt className="text-gray-500">{t('knowledgeExport.summary.replanCount')}</dt>
        <dd>{summary.replan_count}</dd>
        <dt className="text-gray-500">{t('knowledgeExport.summary.latestQuality')}</dt>
        <dd>{latestQuality === null ? t('knowledgeExport.summary.unavailable') : latestQuality}</dd>
      </dl>
    </Card>
  )
}

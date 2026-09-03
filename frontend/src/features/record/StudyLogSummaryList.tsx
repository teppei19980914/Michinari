import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { resolveQualityLabelKey } from './qualityInput'
import type { components } from '../../types/api.d.ts'

type StudyLogRead = components['schemas']['StudyLogRead']
type QualityMetricType = components['schemas']['QualityMetricType']

export type MaterialLabel = { name: string; unitLabel: string; qualityMetricType: QualityMetricType }

/** 実績の読み取り専用表示（SC-08 日次報告閲覧、および進捗のみ登録済で2日以上前の閲覧、
 * 仕様書6.7）。教材名・単位はGET /records/{date}/quotaから取得したものを
 * materialLabels経由で受け取る（当該日の対象教材と一致しない場合は教材IDで代替表示する）。 */
export function StudyLogSummaryList({
  studyLogs,
  materialLabels,
}: {
  studyLogs: StudyLogRead[]
  materialLabels: Map<number, MaterialLabel>
}) {
  if (studyLogs.length === 0) {
    return <p className="text-sm text-gray-500">{t('dailyReportView.studyLog.empty')}</p>
  }

  return (
    <div className="flex flex-col gap-2">
      {studyLogs.map((log) => {
        const label = materialLabels.get(log.material_id)
        return (
          <Card key={log.id}>
            <p className="font-medium text-gray-900">
              {label?.name ?? t('dailyReportView.studyLog.unknownMaterial', { id: log.material_id })}
            </p>
            <dl className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-600 sm:grid-cols-4">
              <div>
                <dt className="text-gray-400">{t('dailyReportView.studyLog.minutes')}</dt>
                <dd>
                  {log.minutes_spent === null
                    ? t('dailyReportView.studyLog.minutesUnavailable')
                    : `${log.minutes_spent}${t('common.unit.minutes')}`}
                </dd>
              </div>
              <div>
                <dt className="text-gray-400">{t('dailyReportView.studyLog.amount')}</dt>
                <dd>
                  {log.amount_completed}
                  {label?.unitLabel ?? ''}
                </dd>
              </div>
              <div>
                <dt className="text-gray-400">{t('dailyReportView.studyLog.cycle')}</dt>
                <dd>{log.cycle_number}</dd>
              </div>
              {log.quality_value !== null && (
                <div>
                  <dt className="text-gray-400">
                    {label
                      ? t(resolveQualityLabelKey(label.qualityMetricType))
                      : t('dailyReportView.studyLog.qualityLabel')}
                  </dt>
                  <dd>{log.quality_value}</dd>
                </div>
              )}
            </dl>
          </Card>
        )
      })}
    </div>
  )
}

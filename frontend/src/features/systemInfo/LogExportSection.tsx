import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { format, subDays } from 'date-fns'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { apiErrorMessage } from '../../api/client'
import { getToday } from '../../api/records'
import { downloadLogExport } from '../../api/systemLogs'
import { downloadBlob } from '../../utils/downloadBlob'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** プリセットの遡り日数（当日を含む日数-1）。UI上の選択肢の一部であり、`app_setting`に
 * 前例のある業務閾値（例: バックアップ保持件数）とは性質が異なるためここへ直接置く
 * （CLAUDE.md「ゼロハードコーディング」は文言・IDの直書き禁止が主旨。ラベル自体は
 * ロケール経由にする）。 */
const PRESETS = [
  { key: 'today', days: 0 },
  { key: 'last3Days', days: 2 },
  { key: 'last7Days', days: 6 },
] as const

type DateRange = { from: string; to: string }

/** 「今日」はサーバの論理日（GET /records/today）を起点にする。CLAUDE.md「クライアント側
 * での論理日の判断」禁止のため、ブラウザの`new Date()`を基準にしてはならない。 */
function presetRange(logicalDate: string, days: number): DateRange {
  return { from: format(subDays(new Date(logicalDate), days), 'yyyy-MM-dd'), to: logicalDate }
}

/** SC-15 診断ログのエクスポート（Phase40 診断ログ出力・トレース強化）。
 *
 * 利用者自身が任意の期間のログを取り出し、サポートへ共有して原因調査を依頼できるように
 * する。期間はプリセット（当日／過去3日／過去7日）またはカレンダー入力で指定する。 */
export function LogExportSection() {
  const { showToast, showApiError } = useToast()
  const todayQuery = useQuery({ queryKey: QUERY_KEYS.today(), queryFn: getToday })
  // 利用者がまだ触れていない間はnull。この間はサーバの論理日から都度既定値を導出する
  // （useEffectでの同期的なsetStateは無駄な再描画を招くため使わない。React公式の
  // 「エフェクトを使わずレンダー中に導出する」指針、oxlint react(set-state-in-effect)）。
  const [range, setRange] = useState<DateRange | null>(null)

  const mutation = useMutation({
    mutationFn: async (selected: DateRange) => {
      const blob = await downloadLogExport(selected.from, selected.to)
      downloadBlob(blob, `michinari-logs_${selected.from}_${selected.to}.log`)
    },
    onSuccess: () => showToast(t('systemInfo.logExport.downloadSucceeded')),
    onError: showApiError,
  })

  if (todayQuery.isLoading) {
    return (
      <Card>
        <p className="text-sm text-gray-500">{t('common.loading')}</p>
      </Card>
    )
  }
  if (todayQuery.isError || !todayQuery.data) {
    return (
      <Card>
        <p className="text-sm text-red-600">{apiErrorMessage(todayQuery.error)}</p>
      </Card>
    )
  }
  const today = todayQuery.data
  const { from: dateFrom, to: dateTo } = range ?? presetRange(today.logical_date, 0)

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('systemInfo.logExport.title')}</h2>
      <p className="text-sm text-gray-500">{t('systemInfo.logExport.description')}</p>
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((preset) => (
          <Button
            key={preset.key}
            variant="secondary"
            onClick={() => setRange(presetRange(today.logical_date, preset.days))}
          >
            {t(`systemInfo.logExport.presets.${preset.key}`)}
          </Button>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('systemInfo.logExport.fromLabel')}
          <Input
            type="date"
            value={dateFrom}
            max={dateTo}
            onChange={(e) => setRange({ from: e.target.value, to: dateTo })}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('systemInfo.logExport.toLabel')}
          <Input
            type="date"
            value={dateTo}
            min={dateFrom}
            onChange={(e) => setRange({ from: dateFrom, to: e.target.value })}
          />
        </label>
        <Button
          disabled={mutation.isPending}
          onClick={() => mutation.mutate({ from: dateFrom, to: dateTo })}
        >
          {t('systemInfo.logExport.downloadButton')}
        </Button>
      </div>
    </Card>
  )
}

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { downloadBlob } from '../../utils/downloadBlob'
import { WorkReportForm } from './WorkReportForm'
import { resolveWorkReportKind } from './workReportKind'
import { useWorkReportDraft } from './useWorkReportDraft'
import { QUERY_KEYS, type WorkReportKind } from '../../constants/queryKeys'

/** 月次報告・半期評価タブ（仕事目標、実装フェーズ分割計画書Phase22・23）。
 *
 * 生成→レビュー用フォーム（その場で編集）→保存→ダウンロード、という流れをkind
 * （monthly/semiannual）で共通化する（CLAUDE.md DRYの原則。「当月/当該半期の目標」は
 * サーバ側が前期のnext_goal_textから複製する値のため、この画面からは編集専用の
 * 表示欄として扱い、AIが再生成する対象ではない。ロジック・プロンプト編17.9「AIの
 * 役割を絞り込む設計」）。
 *
 * 種別ごとの差分は workReportKind.ts、入力値の保持は useWorkReportDraft.ts、入力欄は
 * WorkReportForm.tsx へ切り出してある（CODING_RULES.md「保守性（複雑度）」）。入力値を
 * 保持するフックをこの関数の直下に置くのは、フォームが報告の未取得中は描画されないため
 * である（条件付きで描画される側へ移すと生成のたびに入力内容が失われる）。
 */
export function WorkReportTab({ goalId, kind }: { goalId: number; kind: WorkReportKind }) {
  const queryClient = useQueryClient()
  const { showApiError, showToast } = useToast()
  const [period, setPeriod] = useState('')

  const config = resolveWorkReportKind(kind)
  const queryKey = QUERY_KEYS.workReportPeriod(kind, goalId, period)

  const reportQuery = useQuery({
    queryKey,
    queryFn: () => config.getReport(goalId, period || undefined),
  })
  const report = reportQuery.data
  const draft = useWorkReportDraft(report)

  const generateMutation = useMutation({
    mutationFn: () => config.generateReport(goalId, period || undefined),
    onSuccess: (generated) => {
      draft.applyReport(generated)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workReport(kind, goalId) })
    },
    onError: showApiError,
  })

  const saveMutation = useMutation({
    mutationFn: () => {
      /* v8 ignore next -- 保存ボタンは report があるときしか描画しないため到達しない。
         period_key を取り出すための型の絞り込みであり、テストからは通せない
         （OPERATIONS.md「到達不能な防御的分岐」）。 */
      if (!report) throw new Error('report not loaded')
      const payload = {
        target_goal_text: draft.targetGoalText,
        business_summary: draft.businessSummary,
        achievement_score: draft.achievementScore,
        achievement_reflection: draft.achievementReflection,
        next_goal_text: draft.nextGoalText,
        ...(config.showReportNotes ? { report_notes: draft.reportNotes } : {}),
      }
      return config.updateReport(goalId, report.period_key, payload)
    },
    onSuccess: (saved) => {
      draft.applyReport(saved)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workReport(kind, goalId) })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const handleDownload = () => {
    /* v8 ignore next -- ダウンロードボタンは report があるときしか描画しないため到達しない。
       body / period_key を取り出すための型の絞り込みである（上の saveMutation と同じ）。 */
    if (!report) return
    const blob = new Blob([report.body], { type: 'text/markdown;charset=utf-8' })
    downloadBlob(blob, `${kind}-${report.period_key}.md`)
  }

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t(config.periodLabelKey)}
          <Input
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder={config.periodPlaceholder}
          />
        </label>
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            disabled={generateMutation.isPending}
            onClick={() => generateMutation.mutate()}
          >
            {report ? t('goals.workReport.regenerateButton') : t('goals.workReport.generateButton')}
          </Button>
        </div>
      </Card>

      {reportQuery.isLoading && <p className="text-sm text-gray-500">{t('common.loading')}</p>}

      {!reportQuery.isLoading && !report && (
        <p className="text-sm text-gray-500">{t('goals.workReport.empty')}</p>
      )}

      {report && (
        <WorkReportForm
          draft={draft}
          nextGoalTextLabelKey={config.nextGoalTextLabelKey}
          showReportNotes={config.showReportNotes}
          isSaving={saveMutation.isPending}
          onSave={() => saveMutation.mutate()}
          onDownload={handleDownload}
        />
      )}
    </div>
  )
}

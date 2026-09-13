import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Textarea } from '../../components/Textarea'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { downloadBlob } from '../../utils/downloadBlob'
import {
  generateMonthlyReport,
  generateSemiannualReview,
  getMonthlyReport,
  getSemiannualReview,
  updateMonthlyReport,
  updateSemiannualReview,
  type WorkReportRead,
} from '../../api/closure'
import { QUERY_KEYS, type WorkReportKind } from '../../constants/queryKeys'

const ACHIEVEMENT_SCORES = [1, 2, 3, 4, 5] as const

/** 月次報告・半期評価タブ（仕事目標、実装フェーズ分割計画書Phase22・23）。
 *
 * 生成→レビュー用フォーム（その場で編集）→保存→ダウンロード、という流れをkind
 * （monthly/semiannual）で共通化する（CLAUDE.md DRYの原則。「当月/当該半期の目標」は
 * サーバ側が前期のnext_goal_textから複製する値のため、この画面からは編集専用の
 * 表示欄として扱い、AIが再生成する対象ではない。ロジック・プロンプト編17.9「AIの
 * 役割を絞り込む設計」）。
 */
export function WorkReportTab({ goalId, kind }: { goalId: number; kind: WorkReportKind }) {
  const queryClient = useQueryClient()
  const { showApiError, showToast } = useToast()
  const [period, setPeriod] = useState('')
  const [businessSummary, setBusinessSummary] = useState('')
  const [targetGoalText, setTargetGoalText] = useState('')
  const [achievementScore, setAchievementScore] = useState<number | null>(null)
  const [achievementReflection, setAchievementReflection] = useState('')
  const [nextGoalText, setNextGoalText] = useState('')
  const [reportNotes, setReportNotes] = useState('')

  const getReport = kind === 'monthly' ? getMonthlyReport : getSemiannualReview
  const generateReport = kind === 'monthly' ? generateMonthlyReport : generateSemiannualReview
  const updateReport = kind === 'monthly' ? updateMonthlyReport : updateSemiannualReview
  const queryKey = QUERY_KEYS.workReportPeriod(kind, goalId, period)
  const periodLabelKey =
    kind === 'monthly' ? 'goals.workReport.periodLabelMonthly' : 'goals.workReport.periodLabelSemiannual'
  const periodPlaceholder = kind === 'monthly' ? 'YYYY-MM' : 'YYYY-H1 / YYYY-H2'

  const reportQuery = useQuery({
    queryKey,
    queryFn: () => getReport(goalId, period || undefined),
  })

  const applyReport = (report: WorkReportRead) => {
    setBusinessSummary(report.business_summary ?? '')
    setTargetGoalText(report.target_goal_text ?? '')
    setAchievementScore(report.achievement_score)
    setAchievementReflection(report.achievement_reflection ?? '')
    setNextGoalText(report.next_goal_text ?? '')
    setReportNotes(report.report_notes ?? '')
  }

  useEffect(() => {
    if (reportQuery.data) {
      applyReport(reportQuery.data)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportQuery.data])

  const generateMutation = useMutation({
    mutationFn: () => generateReport(goalId, period || undefined),
    onSuccess: (report) => {
      applyReport(report)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workReport(kind, goalId) })
    },
    onError: showApiError,
  })

  const saveMutation = useMutation({
    mutationFn: () => {
      const report = reportQuery.data
      /* v8 ignore next -- 保存ボタンは report があるときしか描画しないため到達しない。
         period_key を取り出すための型の絞り込みであり、テストからは通せない
         （OPERATIONS.md「到達不能な防御的分岐」）。 */
      if (!report) throw new Error('report not loaded')
      const payload = {
        target_goal_text: targetGoalText,
        business_summary: businessSummary,
        achievement_score: achievementScore,
        achievement_reflection: achievementReflection,
        next_goal_text: nextGoalText,
        ...(kind === 'monthly' ? { report_notes: reportNotes } : {}),
      }
      return updateReport(goalId, report.period_key, payload)
    },
    onSuccess: (report) => {
      applyReport(report)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workReport(kind, goalId) })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const handleDownload = () => {
    /* v8 ignore next -- ダウンロードボタンは report があるときしか描画しないため到達しない。
       body / period_key を取り出すための型の絞り込みである（上の saveMutation と同じ）。 */
    if (!reportQuery.data) return
    const blob = new Blob([reportQuery.data.body], { type: 'text/markdown;charset=utf-8' })
    downloadBlob(blob, `${kind}-${reportQuery.data.period_key}.md`)
  }

  const report = reportQuery.data

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t(periodLabelKey)}
          <Input
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            placeholder={periodPlaceholder}
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
        <Card className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t('goals.workReport.targetGoalTextLabel')}
            <Textarea
              value={targetGoalText}
              onChange={(e) => setTargetGoalText(e.target.value)}
              rows={2}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t('goals.workReport.businessSummaryLabel')}
            <Textarea
              value={businessSummary}
              onChange={(e) => setBusinessSummary(e.target.value)}
              rows={4}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t('goals.workReport.achievementScoreLabel')}
            <select
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={achievementScore ?? ''}
              onChange={(e) =>
                setAchievementScore(e.target.value === '' ? null : Number(e.target.value))
              }
            >
              <option value="">{t('common.unset')}</option>
              {ACHIEVEMENT_SCORES.map((score) => (
                <option key={score} value={score}>
                  {t(`goals.workReport.achievementScore.${score}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t('goals.workReport.achievementReflectionLabel')}
            <Textarea
              value={achievementReflection}
              onChange={(e) => setAchievementReflection(e.target.value)}
              rows={4}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t(
              kind === 'monthly'
                ? 'goals.workReport.nextGoalTextLabelMonthly'
                : 'goals.workReport.nextGoalTextLabelSemiannual',
            )}
            <Textarea
              value={nextGoalText}
              onChange={(e) => setNextGoalText(e.target.value)}
              rows={3}
            />
          </label>
          {kind === 'monthly' && (
            <label className="flex flex-col gap-1 text-sm text-gray-700">
              {t('goals.workReport.reportNotesLabel')}
              <Textarea
                value={reportNotes}
                onChange={(e) => setReportNotes(e.target.value)}
                rows={3}
              />
            </label>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={handleDownload}>
              {t('goals.workReport.downloadButton')}
            </Button>
            <Button disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
              {t('common.action.save')}
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}

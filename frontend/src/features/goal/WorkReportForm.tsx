/** 月次報告・半期評価（WorkReportTab.tsx）のレビュー用フォーム。
 *
 * 1関数100行の上限（CODING_RULES.md「保守性（複雑度）」）を超えていた WorkReportTab から、
 * 生成済みの報告を編集する入力欄を切り出したものである。
 *
 * 入力値は呼び出し元（WorkReportTab 直下の useWorkReportDraft）が保持する。この部品は
 * 報告が未取得のあいだ描画されないため、ここで値を持つと生成のたびに入力内容が失われる。 */
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Textarea } from '../../components/Textarea'
import { Button } from '../../components/Button'
import type { WorkReportDraft } from './useWorkReportDraft'

const ACHIEVEMENT_SCORES = [1, 2, 3, 4, 5] as const

export function WorkReportForm({
  draft,
  nextGoalTextLabelKey,
  showReportNotes,
  isSaving,
  onSave,
  onDownload,
}: {
  draft: WorkReportDraft
  nextGoalTextLabelKey: string
  showReportNotes: boolean
  isSaving: boolean
  onSave: () => void
  onDownload: () => void
}) {
  return (
    <Card className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workReport.targetGoalTextLabel')}
        <Textarea
          value={draft.targetGoalText}
          onChange={(e) => draft.setTargetGoalText(e.target.value)}
          rows={2}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workReport.businessSummaryLabel')}
        <Textarea
          value={draft.businessSummary}
          onChange={(e) => draft.setBusinessSummary(e.target.value)}
          rows={4}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t('goals.workReport.achievementScoreLabel')}
        <select
          className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          value={draft.achievementScore ?? ''}
          onChange={(e) =>
            draft.setAchievementScore(e.target.value === '' ? null : Number(e.target.value))
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
          value={draft.achievementReflection}
          onChange={(e) => draft.setAchievementReflection(e.target.value)}
          rows={4}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-gray-700">
        {t(nextGoalTextLabelKey)}
        <Textarea
          value={draft.nextGoalText}
          onChange={(e) => draft.setNextGoalText(e.target.value)}
          rows={3}
        />
      </label>
      {showReportNotes && (
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          {t('goals.workReport.reportNotesLabel')}
          <Textarea
            value={draft.reportNotes}
            onChange={(e) => draft.setReportNotes(e.target.value)}
            rows={3}
          />
        </label>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onDownload}>
          {t('goals.workReport.downloadButton')}
        </Button>
        <Button disabled={isSaving} onClick={onSave}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}

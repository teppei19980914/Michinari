import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { useToast } from '../../components/Toast'
import { useAiConfigured } from '../../hooks/useAiConfigured'
import { downloadBlob } from '../../utils/downloadBlob'
import {
  generateEvaluationReport,
  listEvaluationReports,
  updateEvaluationReport,
  type WorkEvaluationReportRead,
} from '../../api/closure'
import type { GoalDetailRead } from '../../api/goals'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { WorkEvaluationGenerateCard } from './WorkEvaluationGenerateCard'
import { WorkEvaluationReviewCard } from './WorkEvaluationReviewCard'
import { WorkEvaluationHistoryList } from './WorkEvaluationHistoryList'

/** AI評価レポートタブ（要件定義書6.11、role=EVALUATORの案件のみGoalDetailPageから表示）。
 *
 * 月次報告・半期評価（WorkReportTab）と同じ「生成→レビュー画面で確認・修正→保存→
 * ダウンロード」の流れを踏襲するが、期間ごとの構造化フィールドを持たず本文（body）
 * 1本のみを編集対象とするため、専用のdraftフックは設けない（CLAUDE.md DRYの原則。
 * 使わない機構は作らない）。生成のたびに新規レポートとして履歴に残る（メンバー評価は
 * 時系列の複数回生成に意味があるため、月次/半期報告のような1期間1行upsertとは異なる）。
 * 生成カード・レビューカード・履歴一覧は1関数100行の上限のため別ファイルへ切り出した
 * （CODING_RULES.md「保守性（複雑度）」）。
 */
export function WorkEvaluationReportTab({ goal }: { goal: GoalDetailRead }) {
  const queryClient = useQueryClient()
  const { showApiError, showToast } = useToast()
  const aiConfigured = useAiConfigured()
  const workAssignment = goal.work_assignment

  const [memberId, setMemberId] = useState<number | ''>('')
  const [considerations, setConsiderations] = useState('')
  const [currentReport, setCurrentReport] = useState<WorkEvaluationReportRead | null>(null)
  const [bodyDraft, setBodyDraft] = useState('')

  const historyQuery = useQuery({
    queryKey: QUERY_KEYS.workEvaluationReports(goal.id),
    queryFn: () => listEvaluationReports(goal.id),
  })

  const invalidateHistory = () =>
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workEvaluationReports(goal.id) })

  const generateMutation = useMutation({
    mutationFn: () =>
      generateEvaluationReport(goal.id, { member_id: Number(memberId), considerations }),
    onSuccess: (report) => {
      setCurrentReport(report)
      setBodyDraft(report.body)
      invalidateHistory()
    },
    onError: showApiError,
  })

  const saveMutation = useMutation({
    mutationFn: () => {
      /* v8 ignore next -- 保存ボタンはcurrentReportがあるときしか描画しないため到達しない
         （WorkReportTab.tsxのsaveMutationと同じ型の絞り込み）。 */
      if (!currentReport) throw new Error('report not loaded')
      return updateEvaluationReport(goal.id, currentReport.id, { body: bodyDraft })
    },
    onSuccess: (saved) => {
      setCurrentReport(saved)
      setBodyDraft(saved.body)
      invalidateHistory()
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const handleDownload = () => {
    /* v8 ignore next -- ダウンロードボタンはcurrentReportがあるときしか描画しないため到達しない。 */
    if (!currentReport) return
    const blob = new Blob([bodyDraft], { type: 'text/markdown;charset=utf-8' })
    downloadBlob(blob, `evaluation-report-${currentReport.member_id}-${currentReport.id}.md`)
  }

  if (workAssignment?.role !== 'EVALUATOR') {
    return (
      <p className="text-sm text-gray-500">{t('goals.workEvaluationReport.roleRequiredNotice')}</p>
    )
  }

  const activeMembers = workAssignment.members.filter((member) => member.is_active)

  if (activeMembers.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        {t('goals.workEvaluationReport.memberRequiredNotice')}
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <WorkEvaluationGenerateCard
        activeMembers={activeMembers}
        memberId={memberId}
        onChangeMemberId={setMemberId}
        considerations={considerations}
        onChangeConsiderations={setConsiderations}
        aiConfigured={aiConfigured}
        isPending={generateMutation.isPending}
        onGenerate={() => generateMutation.mutate()}
      />

      {currentReport && (
        <WorkEvaluationReviewCard
          body={bodyDraft}
          onChangeBody={setBodyDraft}
          isSaving={saveMutation.isPending}
          onSave={() => saveMutation.mutate()}
          onDownload={handleDownload}
        />
      )}

      <WorkEvaluationHistoryList
        reports={historyQuery.data ?? []}
        onSelect={(report) => {
          setCurrentReport(report)
          setBodyDraft(report.body)
        }}
      />
    </div>
  )
}

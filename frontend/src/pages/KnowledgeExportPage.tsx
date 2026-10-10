import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { useToast } from '../components/toastContext'
import { apiErrorMessage } from '../api/client'
import { getGoal } from '../api/goals'
import {
  executeKnowledgeExport,
  getKnowledgeExportProgress,
  previewKnowledgeExport,
  type ExportSelection,
} from '../api/export'
import { ExportSelectionCard } from '../features/export/ExportSelectionCard'
import { DEFAULT_SELECTION } from '../features/export/exportSelectionItems'
import { ExportSummaryCard } from '../features/export/ExportSummaryCard'
import { canGenerateRetrospective } from '../features/goal/goalStatus'
import {
  RetrospectiveSection,
  WorkRetrospectivesNote,
} from '../features/export/RetrospectiveSection'
import { QUERY_KEYS } from '../constants/queryKeys'

/** 匿名化の実行中の進捗（完了件数／総数）。進行中のときだけ表示する。 */
function ExportProgressNote({
  progress,
}: {
  progress: Awaited<ReturnType<typeof getKnowledgeExportProgress>> | undefined
}) {
  if (!progress?.in_progress) return null
  return (
    <p className="text-sm text-text-faint">
      {t('knowledgeExport.exportProgress', {
        completed: progress.completed,
        total: progress.total,
      })}
    </p>
  )
}

/** SC-13 ナレッジエクスポート（仕様書6.10）。
 *
 * 出力項目の選択は ExportSelectionCard.tsx、総括レポートは RetrospectiveSection.tsx、
 * 学習サマリは ExportSummaryCard.tsx へ切り出してある（CODING_RULES.md「保守性（複雑度）」）。 */
export function KnowledgeExportPage() {
  const { goalId: goalIdParam } = useParams<{ goalId: string }>()
  const goalId = Number(goalIdParam)
  const { showApiError, showToast } = useToast()

  const [selection, setSelection] = useState<ExportSelection>(DEFAULT_SELECTION)
  const [anonymize, setAnonymize] = useState(false)

  const goalQuery = useQuery({ queryKey: QUERY_KEYS.goal(goalId), queryFn: () => getGoal(goalId) })

  const previewMutation = useMutation({
    mutationFn: () => previewKnowledgeExport(goalId, selection, anonymize),
    meta: { overlay: 'saving' },
    onError: showApiError,
  })

  const exportMutation = useMutation({
    mutationFn: () => executeKnowledgeExport(goalId, { ...selection, anonymize }),
    meta: { overlay: 'saving' },
    onSuccess: () => showToast(t('knowledgeExport.exportSucceeded')),
    onError: showApiError,
  })

  // 匿名化実行中は複数回のAI呼び出しを伴い時間がかかるため進捗をポーリング表示する
  // （実装フェーズ分割計画書Phase10注意点「進捗を表示すること」）。
  const exportProgressQuery = useQuery({
    queryKey: QUERY_KEYS.knowledgeExportProgress(goalId),
    queryFn: () => getKnowledgeExportProgress(goalId),
    enabled: exportMutation.isPending && anonymize,
    refetchInterval: (query) => (query.state.data?.in_progress ? 1000 : false),
  })

  if (goalQuery.isLoading) {
    return <p className="p-6 text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (goalQuery.isError || !goalQuery.data) {
    return <p className="p-6 text-sm text-danger-text">{apiErrorMessage(goalQuery.error)}</p>
  }
  const goal = goalQuery.data
  const isReading = goal.category === 'READING'
  const isWork = goal.category === 'WORK'

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <Link to={ROUTES.goals} className="text-sm text-accent hover:underline">
        {t('knowledgeExport.backToGoal')}
      </Link>

      <h1 className="text-xl font-semibold text-text-primary">
        {t('knowledgeExport.title', { name: goal.name })}
      </h1>

      {isWork ? (
        <WorkRetrospectivesNote />
      ) : (
        <RetrospectiveSection
          goalId={goal.id}
          anonymize={anonymize}
          isReading={isReading}
          canGenerate={canGenerateRetrospective(goal.status)}
        />
      )}
      <ExportSummaryCard
        content={previewMutation.data ?? exportMutation.data}
        isReading={isReading}
        isWork={isWork}
      />

      <ExportSelectionCard
        category={goal.category}
        selection={selection}
        onToggleField={(field, checked) =>
          setSelection((current) => ({ ...current, [field]: checked }))
        }
        anonymize={anonymize}
        onChangeAnonymize={setAnonymize}
      />

      <div className="flex gap-2">
        <Button
          variant="secondary"
          disabled={previewMutation.isPending}
          onClick={() => previewMutation.mutate()}
        >
          {t('knowledgeExport.previewButton')}
        </Button>
        <Button disabled={exportMutation.isPending} onClick={() => exportMutation.mutate()}>
          {t('knowledgeExport.exportButton')}
        </Button>
      </div>

      <ExportProgressNote
        progress={exportMutation.isPending && anonymize ? exportProgressQuery.data : undefined}
      />

      {exportMutation.data && (
        <Card className="flex flex-col gap-1 text-sm text-text-secondary">
          <p>{t('knowledgeExport.exportedPaths.markdown', { path: exportMutation.data.markdown_path })}</p>
          <p>{t('knowledgeExport.exportedPaths.json', { path: exportMutation.data.json_path })}</p>
        </Card>
      )}

      {previewMutation.data && (
        <Card>
          <h2 className="mb-2 font-medium text-text-primary">{t('knowledgeExport.previewTitle')}</h2>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs text-text-secondary">
            {previewMutation.data.markdown}
          </pre>
        </Card>
      )}
    </div>
  )
}

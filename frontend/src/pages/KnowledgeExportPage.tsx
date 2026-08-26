import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { ROUTES } from '../constants/routes'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import { useToast } from '../components/Toast'
import { apiErrorMessage } from '../api/client'
import { getGoal } from '../api/goals'
import { generateRetrospective, getRetrospective } from '../api/closure'
import {
  executeKnowledgeExport,
  getKnowledgeExportProgress,
  previewKnowledgeExport,
  type ExportSelection,
  type KnowledgeExportContentRead,
} from '../api/export'
import {
  computeLatestQualityValue,
  type ExportSummary,
  type QualityTrendEntry,
} from '../features/export/knowledgeExportSummary'

const DEFAULT_SELECTION: ExportSelection = {
  goal_overview: true,
  materials: true,
  summary: true,
  daily_records: true,
  quality_trend: true,
  replan_history: true,
  weekly_summaries: true,
  diary: false,
  ai_dialogue: false,
  exam_results: true,
  retrospective: true,
}

const SELECTION_ITEMS: { field: keyof ExportSelection; labelKey: string }[] = [
  { field: 'goal_overview', labelKey: 'knowledgeExport.selection.goalOverview' },
  { field: 'materials', labelKey: 'knowledgeExport.selection.materials' },
  { field: 'summary', labelKey: 'knowledgeExport.selection.summary' },
  { field: 'daily_records', labelKey: 'knowledgeExport.selection.dailyRecords' },
  { field: 'quality_trend', labelKey: 'knowledgeExport.selection.qualityTrend' },
  { field: 'replan_history', labelKey: 'knowledgeExport.selection.replanHistory' },
  { field: 'weekly_summaries', labelKey: 'knowledgeExport.selection.weeklySummaries' },
  { field: 'diary', labelKey: 'knowledgeExport.selection.diary' },
  { field: 'ai_dialogue', labelKey: 'knowledgeExport.selection.aiDialogue' },
  { field: 'exam_results', labelKey: 'knowledgeExport.selection.examResults' },
  { field: 'retrospective', labelKey: 'knowledgeExport.selection.retrospective' },
]

function RetrospectiveSection({ goalId, anonymize }: { goalId: number; anonymize: boolean }) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const retrospectiveQuery = useQuery({
    queryKey: ['retrospective', goalId, anonymize],
    queryFn: () => getRetrospective(goalId, anonymize),
  })

  const mutation = useMutation({
    mutationFn: () => generateRetrospective(goalId, anonymize),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['retrospective', goalId] })
    },
    onError: showApiError,
  })

  const body = retrospectiveQuery.data?.body ?? null

  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-gray-900">{t('knowledgeExport.retrospective.title')}</h2>
      {mutation.isPending ? (
        <p className="text-sm text-gray-500">{t('knowledgeExport.retrospective.generating')}</p>
      ) : body ? (
        <p className="whitespace-pre-wrap text-sm text-gray-700">{body}</p>
      ) : (
        <p className="text-sm text-gray-500">{t('knowledgeExport.retrospective.empty')}</p>
      )}
      <div>
        <Button
          variant="secondary"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {body
            ? t('knowledgeExport.retrospective.regenerateButton')
            : t('knowledgeExport.retrospective.generateButton')}
        </Button>
      </div>
    </Card>
  )
}

function SummarySection({ content }: { content: KnowledgeExportContentRead | undefined }) {
  if (!content?.data.summary) {
    return null
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

/** SC-13 ナレッジエクスポート（仕様書6.10）。 */
export function KnowledgeExportPage() {
  const { goalId: goalIdParam } = useParams<{ goalId: string }>()
  const goalId = Number(goalIdParam)
  const { showApiError, showToast } = useToast()

  const [selection, setSelection] = useState<ExportSelection>(DEFAULT_SELECTION)
  const [anonymize, setAnonymize] = useState(false)

  const goalQuery = useQuery({ queryKey: ['goal', goalId], queryFn: () => getGoal(goalId) })

  const previewMutation = useMutation({
    mutationFn: () => previewKnowledgeExport(goalId, selection, anonymize),
    onError: showApiError,
  })

  const exportMutation = useMutation({
    mutationFn: () => executeKnowledgeExport(goalId, { ...selection, anonymize }),
    onSuccess: () => showToast(t('knowledgeExport.exportSucceeded')),
    onError: showApiError,
  })

  // 匿名化実行中は複数回のAI呼び出しを伴い時間がかかるため進捗をポーリング表示する
  // （実装フェーズ分割計画書Phase10注意点「進捗を表示すること」）。
  const exportProgressQuery = useQuery({
    queryKey: ['knowledgeExportProgress', goalId],
    queryFn: () => getKnowledgeExportProgress(goalId),
    enabled: exportMutation.isPending && anonymize,
    refetchInterval: (query) => (query.state.data?.in_progress ? 1000 : false),
  })

  if (goalQuery.isLoading) {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (goalQuery.isError || !goalQuery.data) {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(goalQuery.error)}</p>
  }
  const goal = goalQuery.data

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <Link to={ROUTES.goals} className="text-sm text-blue-600 hover:underline">
        {t('knowledgeExport.backToGoal')}
      </Link>

      <h1 className="text-xl font-semibold text-gray-900">
        {t('knowledgeExport.title', { name: goal.name })}
      </h1>

      <RetrospectiveSection goalId={goal.id} anonymize={anonymize} />
      <SummarySection content={previewMutation.data ?? exportMutation.data} />

      <Card className="flex flex-col gap-2">
        <h2 className="font-medium text-gray-900">{t('knowledgeExport.selection.title')}</h2>
        <div className="grid grid-cols-2 gap-1">
          {SELECTION_ITEMS.map((item) => (
            <label key={item.field} className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={selection[item.field]}
                onChange={(e) =>
                  setSelection((current) => ({ ...current, [item.field]: e.target.checked }))
                }
              />
              {t(item.labelKey)}
            </label>
          ))}
        </div>
        <label className="mt-2 flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={anonymize}
            onChange={(e) => setAnonymize(e.target.checked)}
          />
          {t('knowledgeExport.anonymize.label')}
        </label>
        <p className="text-xs text-gray-500">{t('knowledgeExport.anonymize.description')}</p>
      </Card>

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

      {exportMutation.isPending && anonymize && exportProgressQuery.data?.in_progress && (
        <p className="text-sm text-gray-500">
          {t('knowledgeExport.exportProgress', {
            completed: exportProgressQuery.data.completed,
            total: exportProgressQuery.data.total,
          })}
        </p>
      )}

      {exportMutation.data && (
        <Card className="flex flex-col gap-1 text-sm text-gray-700">
          <p>{t('knowledgeExport.exportedPaths.markdown', { path: exportMutation.data.markdown_path })}</p>
          <p>{t('knowledgeExport.exportedPaths.json', { path: exportMutation.data.json_path })}</p>
        </Card>
      )}

      {previewMutation.data && (
        <Card>
          <h2 className="mb-2 font-medium text-gray-900">{t('knowledgeExport.previewTitle')}</h2>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs text-gray-700">
            {previewMutation.data.markdown}
          </pre>
        </Card>
      )}
    </div>
  )
}

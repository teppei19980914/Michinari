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
  type ReadingExportSummary,
  type WorkExportSummary,
} from '../features/export/knowledgeExportSummary'
import { QUERY_KEYS } from '../constants/queryKeys'

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

/** 教材構成・品質指標推移・リプラン履歴・週次要約・日記本文・AI対話履歴・受験結果は、
 * 読書目標・仕事目標には該当データが無いため選択肢自体を表示しない（仕様書6.10「読書目標の
 * 場合」「仕事目標の場合」、設計書データ構造編7.1）。summary・daily_records・retrospectiveは
 * 読書・仕事それぞれの読み替えラベルを別途表示する。 */
const SELECTION_ITEMS: {
  field: keyof ExportSelection
  labelKey: string
  readingLabelKey?: string
  workLabelKey?: string
  hiddenForReadingOrWork?: boolean
}[] = [
  { field: 'goal_overview', labelKey: 'knowledgeExport.selection.goalOverview' },
  {
    field: 'materials',
    labelKey: 'knowledgeExport.selection.materials',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'summary',
    labelKey: 'knowledgeExport.selection.summary',
    readingLabelKey: 'knowledgeExport.selection.readingSummary',
    workLabelKey: 'knowledgeExport.selection.workSummary',
  },
  {
    field: 'daily_records',
    labelKey: 'knowledgeExport.selection.dailyRecords',
    readingLabelKey: 'knowledgeExport.selection.readingDailyRecords',
    workLabelKey: 'knowledgeExport.selection.workDailyRecords',
  },
  {
    field: 'quality_trend',
    labelKey: 'knowledgeExport.selection.qualityTrend',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'replan_history',
    labelKey: 'knowledgeExport.selection.replanHistory',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'weekly_summaries',
    labelKey: 'knowledgeExport.selection.weeklySummaries',
    hiddenForReadingOrWork: true,
  },
  { field: 'diary', labelKey: 'knowledgeExport.selection.diary', hiddenForReadingOrWork: true },
  {
    field: 'ai_dialogue',
    labelKey: 'knowledgeExport.selection.aiDialogue',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'exam_results',
    labelKey: 'knowledgeExport.selection.examResults',
    hiddenForReadingOrWork: true,
  },
  {
    field: 'retrospective',
    labelKey: 'knowledgeExport.selection.retrospective',
    readingLabelKey: 'knowledgeExport.selection.readingRetrospective',
    workLabelKey: 'knowledgeExport.selection.workRetrospective',
  },
]

function RetrospectiveSection({
  goalId,
  anonymize,
  isReading,
}: {
  goalId: number
  anonymize: boolean
  isReading: boolean
}) {
  const queryClient = useQueryClient()
  const { showApiError } = useToast()
  const retrospectiveQuery = useQuery({
    queryKey: QUERY_KEYS.retrospectiveView(goalId, anonymize),
    queryFn: () => getRetrospective(goalId, anonymize),
  })

  const mutation = useMutation({
    mutationFn: () => generateRetrospective(goalId, anonymize),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.retrospective(goalId) })
    },
    onError: showApiError,
  })

  const body = retrospectiveQuery.data?.body ?? null

  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-gray-900">
        {t(
          isReading ? 'knowledgeExport.retrospective.readingTitle' : 'knowledgeExport.retrospective.title',
        )}
      </h2>
      {mutation.isPending ? (
        <p className="text-sm text-gray-500">{t('knowledgeExport.retrospective.generating')}</p>
      ) : body ? (
        <p className="whitespace-pre-wrap text-sm text-gray-700">{body}</p>
      ) : (
        <p className="text-sm text-gray-500">
          {t(
            isReading ? 'knowledgeExport.retrospective.readingEmpty' : 'knowledgeExport.retrospective.empty',
          )}
        </p>
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

/** 仕事目標では、月次報告・半期評価（複数期間分）は既存の総括レポート専用エンドポイント
 * （generateRetrospective/getRetrospective）を使えない（総括レポートは仕事目標を恒久的に
 * 拒否する。データ構造編6.2）。生成・編集は目標詳細画面の月次報告・半期評価タブ
 * （WorkReportTab）で行う設計のため、本画面では案内文のみを表示し、実際の内容は
 * プレビュー・エクスポート結果のMarkdown全文（retrospective選択時）で確認する。 */
function WorkRetrospectivesNote() {
  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-medium text-gray-900">
        {t('knowledgeExport.retrospective.workTitle')}
      </h2>
      <p className="text-sm text-gray-500">{t('knowledgeExport.retrospective.workNotice')}</p>
    </Card>
  )
}

function SummarySection({
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

/** SC-13 ナレッジエクスポート（仕様書6.10）。 */
export function KnowledgeExportPage() {
  const { goalId: goalIdParam } = useParams<{ goalId: string }>()
  const goalId = Number(goalIdParam)
  const { showApiError, showToast } = useToast()

  const [selection, setSelection] = useState<ExportSelection>(DEFAULT_SELECTION)
  const [anonymize, setAnonymize] = useState(false)

  const goalQuery = useQuery({ queryKey: QUERY_KEYS.goal(goalId), queryFn: () => getGoal(goalId) })

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
    queryKey: QUERY_KEYS.knowledgeExportProgress(goalId),
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
  const isReading = goal.category === 'READING'
  const isWork = goal.category === 'WORK'
  const visibleSelectionItems = SELECTION_ITEMS.filter(
    (item) => !((isReading || isWork) && item.hiddenForReadingOrWork),
  )

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <Link to={ROUTES.goals} className="text-sm text-blue-600 hover:underline">
        {t('knowledgeExport.backToGoal')}
      </Link>

      <h1 className="text-xl font-semibold text-gray-900">
        {t('knowledgeExport.title', { name: goal.name })}
      </h1>

      {isWork ? (
        <WorkRetrospectivesNote />
      ) : (
        <RetrospectiveSection goalId={goal.id} anonymize={anonymize} isReading={isReading} />
      )}
      <SummarySection
        content={previewMutation.data ?? exportMutation.data}
        isReading={isReading}
        isWork={isWork}
      />

      <Card className="flex flex-col gap-2">
        <h2 className="font-medium text-gray-900">{t('knowledgeExport.selection.title')}</h2>
        <div className="grid grid-cols-2 gap-1">
          {visibleSelectionItems.map((item) => {
            const labelKey = isWork
              ? (item.workLabelKey ?? item.labelKey)
              : isReading
                ? (item.readingLabelKey ?? item.labelKey)
                : item.labelKey
            return (
              <label key={item.field} className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={selection[item.field]}
                  onChange={(e) =>
                    setSelection((current) => ({ ...current, [item.field]: e.target.checked }))
                  }
                />
                {t(labelKey)}
              </label>
            )
          })}
        </div>
        <label className="mt-2 flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={anonymize}
            onChange={(e) => setAnonymize(e.target.checked)}
          />
          {t('knowledgeExport.anonymize.label')}
        </label>
        <p className="text-xs text-gray-500">
          {t(
            isWork
              ? 'knowledgeExport.anonymize.workDescription'
              : isReading
                ? 'knowledgeExport.anonymize.readingDescription'
                : 'knowledgeExport.anonymize.description',
          )}
        </p>
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

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { t } from '../locales/t'
import { Card } from '../components/Card'
import { MarkdownText } from '../components/MarkdownText'
import { useToast } from '../components/toastContext'
import { apiErrorMessage } from '../api/client'
import {
  getRecapTheme,
  listRecapThemes,
  mergeRecapTheme,
  rebuildRecapTheme,
  renameRecapTheme,
  type RecapThemeDetail,
} from '../api/recap'
import { RecapThemeEditCard } from '../features/recap/RecapThemeEditCard'
import { RecapThemeEntriesCard } from '../features/recap/RecapThemeEntriesCard'
import { QUERY_KEYS } from '../constants/queryKeys'
import { ROUTE_PATTERNS, ROUTES } from '../constants/routes'

/** 振り返りテーマの詳細（仕様書6.1.3）。累積本文と、紐付く報告（日付順）を表示する。 */
export function RecapThemeDetailPage() {
  const { themeId: themeIdParam } = useParams<{ themeId: string }>()
  const themeId = Number(themeIdParam)
  const detailQuery = useQuery({
    queryKey: QUERY_KEYS.recapTheme(themeId),
    queryFn: () => getRecapTheme(themeId),
  })

  if (detailQuery.isLoading) {
    return <p className="text-sm text-text-faint">{t('common.loading')}</p>
  }
  if (detailQuery.isError || !detailQuery.data) {
    return <p className="text-sm text-red-600">{apiErrorMessage(detailQuery.error)}</p>
  }
  return <RecapThemeDetailContent theme={detailQuery.data} />
}

function RecapThemeDetailContent({ theme }: { theme: RecapThemeDetail }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const siblingsQuery = useQuery({
    queryKey: QUERY_KEYS.recapThemes(theme.goal_id),
    queryFn: () => listRecapThemes(theme.goal_id),
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.recapTheme(theme.id) })
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.recapThemes(theme.goal_id) })
  }

  const renameMutation = useMutation({
    mutationFn: (name: string) => renameRecapTheme(theme.id, name),
    onSuccess: () => {
      invalidate()
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const mergeMutation = useMutation({
    mutationFn: (targetThemeId: number) => mergeRecapTheme(theme.id, targetThemeId),
    onSuccess: (merged) => {
      invalidate()
      showToast(t('common.saveSucceeded'))
      navigate(ROUTES.recapTheme(merged.id), { replace: true })
    },
    onError: showApiError,
  })

  const rebuildMutation = useMutation({
    mutationFn: () => rebuildRecapTheme(theme.id),
    meta: { overlay: 'saving' },
    onSuccess: () => {
      invalidate()
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const mergeCandidates = (siblingsQuery.data ?? []).filter((item) => item.id !== theme.id)
  const isSaving = renameMutation.isPending || mergeMutation.isPending || rebuildMutation.isPending

  return (
    <div className="flex flex-col gap-3">
      <Link className="text-sm text-accent-muted-text underline" to={ROUTE_PATTERNS.dashboard}>
        {t('recapTheme.backToDashboard')}
      </Link>
      <Card className="flex flex-col gap-2">
        <h1 className="text-lg font-semibold text-text-primary">{theme.name}</h1>
        {theme.body.trim() === '' ? (
          <p className="text-sm text-text-faint">{t('recapTheme.bodyEmpty')}</p>
        ) : (
          <MarkdownText text={theme.body} className="text-text-primary" />
        )}
      </Card>
      <RecapThemeEditCard
        themeName={theme.name}
        mergeCandidates={mergeCandidates}
        isSaving={isSaving}
        onRename={(name) => renameMutation.mutate(name)}
        onMerge={(targetThemeId) => mergeMutation.mutate(targetThemeId)}
        onRebuild={() => rebuildMutation.mutate()}
      />
      <RecapThemeEntriesCard entries={theme.entries} />
    </div>
  )
}

import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../locales/t'
import { apiErrorMessage } from '../api/client'
import { useToast } from '../components/Toast'
import { Button } from '../components/Button'
import { ROUTES } from '../constants/routes'
import { QUERY_KEYS } from '../constants/queryKeys'
import { getToday, registerProgress } from '../api/records'
import { ProgressLogSections } from '../features/record/ProgressLogSections'
import { toCategoryReportedState } from '../features/record/categoryCompletion'
import { resolveProgressOnlyGuard } from '../features/record/resolveProgressOnlyGuard'
import { resolveProgressOnlyInput } from '../features/record/resolveProgressOnlyInput'
import { resolveVisibleReportTargets } from '../features/record/resolveVisibleReportTargets'
import { useDailyRecordQueries } from '../features/record/useDailyRecordQueries'
import { useDailyReportDraft } from '../features/record/useDailyReportDraft'
import { useSlotNames } from '../features/record/useSlotNames'
import { invalidateDailyRecordCaches } from '../features/record/invalidateDailyRecordCaches'

/** SC-07 進捗のみ登録（仕様書6.6）。実績入力領域のみを持ち、日記記述・AI対話領域は持たない。
 *
 * 実績入力の構成は日次報告（SC-06）と共通のため、資格試験・読書・仕事の3カテゴリを扱う
 * （仕様書6.6「実績入力の構成は6.5と共通とする」、1.1（改21））。サーバのregister_progressは
 * 以前から3カテゴリを1リクエストで受け付けており、資格試験しか送らない実装だったため、
 * 読書・仕事の目標しか持たない利用者には入力欄の無い画面が表示されていた。
 *
 * 日次報告と違い、確定（finalize）もAI対話も持たないため目標タブは設けない。タブは対話と確定を
 * 1目標へ絞るための仕組みであり（仕様書6.5）、登録が1操作で全カテゴリ分をまとめて送る本画面
 * では絞り込む必要がないためである。
 *
 * 「確定前に画面を離脱した場合の警告」（仕様書6.5）はSC-06の完了条件としてのみ明記されており、
 * SC-07には記載がないため、本画面には離脱警告（useLeaveConfirm）を設けていない。 */
export function ProgressOnlyPage() {
  const { date } = useParams<{ date: string }>()
  const targetDate = date as string
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const slotNames = useSlotNames()
  const { showApiError } = useToast()

  const queries = useDailyRecordQueries(targetDate)
  // 進捗のみ登録が可能なのは未来日以外（仕様書7.2「当日または前日以前」）。論理的な本日は
  // クライアントで算出せずサーバから取得する（技術選定書7.1「禁止事項」）。
  const todayQuery = useQuery({ queryKey: QUERY_KEYS.today(), queryFn: getToday })
  // 目標タブを持たないため、初期表示するタブの設定関数は渡さない。SC-06とは別画面のため、
  // storeKeyの接頭辞を分けて下書きを独立させる（useDailyReportDraftのコメント参照）。
  const draft = useDailyReportDraft(`progress-only:${targetDate}`, queries)

  // 目標タブが無い（showGoalSelector=false）ため、着手中の全目標の入力対象がそのまま返る。
  const targets = resolveVisibleReportTargets({
    showGoalSelector: false,
    selectedGoal: undefined,
    goals: queries.goals.data ?? [],
    quotaItems: queries.quota.data ?? [],
    readingBooks: queries.readingBooks.data ?? [],
    workAssignments: queries.workAssignments.data ?? [],
  })
  const input = resolveProgressOnlyInput({
    sections: targets,
    reported: toCategoryReportedState(queries.record.data),
    draft,
  })

  const registerMutation = useMutation({
    mutationFn: () => registerProgress(targetDate, input.payload),
    onSuccess: () => {
      invalidateDailyRecordCaches(queryClient, targetDate)
      navigate(ROUTES.dashboard)
    },
    onError: showApiError,
  })

  // 表示状態（ローディング/エラー/閲覧画面への転送/入力可）の判定はresolveProgressOnlyGuardへ
  // 集約している。全フックの呼び出しが済んだ後で評価する必要があるため、ここで呼ぶ。
  const guard = resolveProgressOnlyGuard(
    { ...queries, today: todayQuery },
    targets.presence,
    targetDate,
  )
  if (guard.kind === 'LOADING') {
    return <p className="p-6 text-sm text-gray-500">{t('common.loading')}</p>
  }
  if (guard.kind === 'ERROR') {
    return <p className="p-6 text-sm text-red-600">{apiErrorMessage(guard.error)}</p>
  }
  if (guard.kind === 'REDIRECT_VIEW') {
    return <Navigate to={ROUTES.dailyReportView(targetDate)} replace />
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold text-gray-900">
        {t('progressOnly.title', { date: targetDate })}
      </h1>

      <ProgressLogSections
        targetDate={targetDate}
        input={input}
        targets={targets}
        quotaItems={guard.quota}
        draft={draft}
        slotNames={slotNames}
      />

      <div className="flex justify-end">
        <Button
          disabled={registerMutation.isPending || !input.canRegister}
          onClick={() => registerMutation.mutate()}
        >
          {t('progressOnly.registerButton')}
        </Button>
      </div>
    </div>
  )
}

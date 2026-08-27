import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Card } from '../../components/Card'
import { Input } from '../../components/Input'
import { Button } from '../../components/Button'
import { useToast } from '../../components/Toast'
import { getAiStatus, listAssistants, loginAi } from '../../api/ai'
import { updateSettings, type AppSettingsRead } from '../../api/settings'
import { resolveReauthOutcome } from './aiReauthOutcome'

const ASSISTANT_FIELDS = [
  { field: 'assistant_uid_daily_feedback', labelKey: 'settings.aiConnection.assistant.dailyFeedback' },
  { field: 'assistant_uid_weekly_summary', labelKey: 'settings.aiConnection.assistant.weeklySummary' },
  { field: 'assistant_uid_daily_message', labelKey: 'settings.aiConnection.assistant.dailyMessage' },
  {
    field: 'assistant_uid_goal_retrospective',
    labelKey: 'settings.aiConnection.assistant.goalRetrospective',
  },
] as const

/** AI接続設定（仕様書6.11。Phase7完了条件「アシスタントが用途ごとに一覧から選択できる
 * （識別子の手入力を求めない）」）。接続用パラメータはHost・PATのみに絞る（UIの簡素化）。
 * client_id・tenant_id・api_base_urlはEntraIDフォールバック認証専用で通常は空でよいため
 * 画面上には出さない（設計書 ロジック・プロンプト編16.2、データ構造編228〜229行）。 */
export function AiConnectionSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const assistantsQuery = useQuery({ queryKey: ['ai-assistants'], queryFn: listAssistants })
  const statusQuery = useQuery({ queryKey: ['ai-status'], queryFn: getAiStatus })

  const [form, setForm] = useState(settings.ai_connection)
  const [pat, setPat] = useState('')

  const saveMutation = useMutation({
    mutationFn: () => updateSettings({ ai_connection: form }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const loginMutation = useMutation({
    mutationFn: () => loginAi({ host: form.host || null, personal_access_token: pat }),
    onSuccess: (result) => {
      setPat('')
      queryClient.invalidateQueries({ queryKey: ['ai-status'] })
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      const outcome = resolveReauthOutcome(result)
      showToast(
        outcome === 'succeeded'
          ? t('settings.aiConnection.authStatus.reauthSucceeded')
          : t('settings.aiConnection.authStatus.reauthFailed'),
        outcome === 'succeeded' ? 'info' : 'error',
      )
    },
    onError: showApiError,
  })

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium text-gray-900">{t('settings.aiConnection.title')}</h2>

      <div className="rounded-md border border-gray-200 p-3">
        <h3 className="text-sm font-medium text-gray-900">
          {t('settings.aiConnection.authStatus.title')}
        </h3>
        <p className="mt-1 text-sm text-gray-600">
          {statusQuery.data?.authenticated
            ? t('settings.aiConnection.authStatus.authenticated')
            : t('settings.aiConnection.authStatus.notAuthenticated')}
        </p>
        {statusQuery.data?.login_in_progress && (
          <p className="text-xs text-gray-500">
            {t('settings.aiConnection.authStatus.loginInProgress')}
          </p>
        )}
        {statusQuery.data && Object.keys(statusQuery.data.model_status).length > 0 && (
          <div className="mt-2 text-xs text-gray-500">
            <p>{t('settings.aiConnection.modelStatusTitle')}</p>
            <ul>
              {Object.entries(statusQuery.data.model_status).map(([model, ok]) => (
                <li key={model}>
                  {model}: {ok ? '✓' : '×'}
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t('settings.aiConnection.hostLabel')}
            <Input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            {t('settings.aiConnection.authStatus.patLabel')}
            <Input type="password" value={pat} onChange={(e) => setPat(e.target.value)} />
          </label>
          <Button
            disabled={loginMutation.isPending || !pat}
            onClick={() => loginMutation.mutate()}
          >
            {t('settings.aiConnection.authStatus.reauth')}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.aiConnection.folderPrefixLabel')}
          <Input
            value={form.folder_prefix}
            onChange={(e) => setForm({ ...form, folder_prefix: e.target.value })}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.aiConnection.timeoutSecondsLabel')}
          <Input
            type="number"
            min={1}
            value={form.timeout_seconds}
            onChange={(e) => setForm({ ...form, timeout_seconds: Number(e.target.value) })}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
          {t('settings.aiConnection.minIntervalSecondsLabel')}
          <Input
            type="number"
            min={0}
            value={form.min_interval_seconds}
            onChange={(e) => setForm({ ...form, min_interval_seconds: Number(e.target.value) })}
          />
        </label>
      </div>

      {assistantsQuery.isLoading && (
        <p className="text-xs text-gray-500">{t('settings.aiConnection.assistant.loading')}</p>
      )}
      {assistantsQuery.isError && (
        <p className="text-xs text-red-600">{t('settings.aiConnection.assistant.loadFailed')}</p>
      )}
      <div className="flex flex-wrap gap-3">
        {ASSISTANT_FIELDS.map(({ field, labelKey }) => (
          <label key={field} className="flex flex-1 flex-col gap-1 text-sm text-gray-700">
            {t(labelKey)}
            <select
              className="rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={form[field]}
              onChange={(e) => setForm({ ...form, [field]: e.target.value })}
            >
              {!form[field] && <option value="">{t('common.unset')}</option>}
              {assistantsQuery.data?.map((assistant) => (
                <option key={assistant.uid} value={assistant.uid}>
                  {assistant.name}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <div className="flex justify-end">
        <Button disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}

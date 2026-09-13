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
import { AiAssistantFields } from './AiAssistantFields'
import { AiAuthStatusCard } from './AiAuthStatusCard'
import { QUERY_KEYS } from '../../constants/queryKeys'

/** AI接続設定（仕様書6.11）。
 *
 * 認証状況と再認証は AiAuthStatusCard.tsx、用途ごとのアシスタント選択は
 * AiAssistantFields.tsx へ切り出してある（CODING_RULES.md「保守性（複雑度）」）。
 * この関数は設定値の保持と保存・再認証の実行を担う。 */
export function AiConnectionSection({ settings }: { settings: AppSettingsRead }) {
  const queryClient = useQueryClient()
  const { showToast, showApiError } = useToast()
  const assistantsQuery = useQuery({ queryKey: QUERY_KEYS.aiAssistants(), queryFn: listAssistants })
  const statusQuery = useQuery({ queryKey: QUERY_KEYS.aiStatus(), queryFn: getAiStatus })

  const [form, setForm] = useState(settings.ai_connection)

  const saveMutation = useMutation({
    mutationFn: () => updateSettings({ ai_connection: form }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
      showToast(t('common.saveSucceeded'))
    },
    onError: showApiError,
  })

  const loginMutation = useMutation({
    mutationFn: (variables: { token: string; clearToken: () => void }) =>
      loginAi({ host: form.host || null, personal_access_token: variables.token }),
    onSuccess: (result, variables) => {
      // 個人アクセストークンは再認証にだけ使う値のため、成功したら入力欄から消す。
      variables.clearToken()
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.aiStatus() })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
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

      <AiAuthStatusCard
        status={statusQuery.data}
        host={form.host}
        onChangeHost={(host) => setForm({ ...form, host })}
        isReauthenticating={loginMutation.isPending}
        onReauthenticate={(token, clearToken) => loginMutation.mutate({ token, clearToken })}
      />

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
      <AiAssistantFields
        values={form}
        assistants={assistantsQuery.data}
        onChange={(field, uid) => setForm({ ...form, [field]: uid })}
      />

      <div className="flex justify-end">
        <Button disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
          {t('common.action.save')}
        </Button>
      </div>
    </Card>
  )
}

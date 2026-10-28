import { useMutation, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Button } from '../../components/Button'
import { useToast } from '../../components/toastContext'
import { updateSettings } from '../../api/settings'
import { syncAutostart } from '../../api/desktop'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { resolveAutostartSyncMessageKey } from '../desktop/reminderOnboarding'

/**
 * 既存利用者向け「アプリが起動していないと通知は届きません」案内（開発Todo
 * リマインド導線 D1・D5）。記録リマインドがオンかつWindows自動起動がオフの間、一度だけ
 * ダッシュボードに表示される（表示条件は`GET /dashboard`の`show_reminder_autostart_banner`）。
 */
export function AutostartBanner({ show }: { show: boolean }) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboard() })
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
  }

  const enableMutation = useMutation({
    mutationFn: async () => {
      await updateSettings({ desktop: { launch_at_login: true } })
      return syncAutostart()
    },
    meta: { overlay: 'saving' },
    onSuccess: (result) => {
      const outcome = resolveAutostartSyncMessageKey(result)
      if (outcome.messageKey) {
        showToast(t(outcome.messageKey), outcome.kind === 'error' ? 'error' : 'info')
      } else {
        showToast(t('common.saveSucceeded'))
      }
      invalidate()
    },
  })

  const dismissMutation = useMutation({
    mutationFn: () => updateSettings({ desktop: { autostart_banner_dismissed: true } }),
    onSuccess: invalidate,
  })

  if (!show) {
    return null
  }

  const isPending = enableMutation.isPending || dismissMutation.isPending

  return (
    <div className="flex items-center justify-between gap-3 rounded-md bg-accent-muted-bg p-3 text-sm text-accent-muted-text">
      <p>{t('dashboard.autostartBanner.description')}</p>
      <div className="flex items-center gap-2">
        <Button disabled={isPending} onClick={() => enableMutation.mutate()}>
          {t('dashboard.autostartBanner.enable')}
        </Button>
        <button
          type="button"
          disabled={isPending}
          onClick={() => dismissMutation.mutate()}
          aria-label={t('dashboard.autostartBanner.dismiss')}
          className="text-accent-muted-text hover:opacity-70 disabled:opacity-50"
        >
          ×
        </button>
      </div>
    </div>
  )
}

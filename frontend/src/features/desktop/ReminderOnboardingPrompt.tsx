import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { t } from '../../locales/t'
import { Modal } from '../../components/Modal'
import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { useToast } from '../../components/toastContext'
import { getSettings, updateSettings } from '../../api/settings'
import { syncAutostart } from '../../api/desktop'
import { QUERY_KEYS } from '../../constants/queryKeys'
import { isValidNotificationTime, resolveAutostartSyncMessageKey } from './reminderOnboarding'

/**
 * 新規利用者向け「毎晩、記録のお知らせを受け取りますか」の1問案内（開発Todo
 * リマインド導線 D1〜D4）。目標が1件以上あり、かつ`desktop.reminder_onboarding_shown`が
 * falseの間、ダッシュボード画面のマウント時に表示される（表示条件は`GET /dashboard`の
 * `show_reminder_onboarding_prompt`）。
 *
 * 「受け取る」を選ぶと、記録リマインド・時刻・Windows自動起動を一括でオンにする。
 * 自動起動が必要な理由（アプリが起動していないと通知が届かない）はヘルプ本文
 * （`help.sections.desktop`）に委ね、ここでは案内文のみ短く示す。
 */
export function ReminderOnboardingPrompt({ open }: { open: boolean }) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const settingsQuery = useQuery({
    queryKey: QUERY_KEYS.settings(),
    queryFn: getSettings,
    enabled: open,
  })
  // null は「利用者がまだ時刻を編集していない」ことを表す。その間は、読み込めた設定の
  // 現在値（既定はいまのリマインド時刻）を都度表示する（setStateをuseEffectで行わない）。
  const [editedTime, setEditedTime] = useState<string | null>(null)
  const notificationTime = editedTime ?? settingsQuery.data?.desktop.notification_time ?? null

  const afterAnswer = () => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboard() })
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.settings() })
  }

  const acceptMutation = useMutation({
    mutationFn: async (time: string) => {
      await updateSettings({
        desktop: {
          notification_enabled: true,
          notification_time: time,
          launch_at_login: true,
          reminder_onboarding_shown: true,
        },
      })
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
      afterAnswer()
    },
  })

  const declineMutation = useMutation({
    mutationFn: () => updateSettings({ desktop: { reminder_onboarding_shown: true } }),
    meta: { overlay: 'saving' },
    onSuccess: afterAnswer,
  })

  const isPending = acceptMutation.isPending || declineMutation.isPending
  const timeIsValid = notificationTime !== null && isValidNotificationTime(notificationTime)

  return (
    <Modal open={open} onClose={() => declineMutation.mutate()} title={t('desktop.onboardingPrompt.title')}>
      <div className="flex flex-col gap-3">
        <p className="text-sm text-text-secondary">{t('desktop.onboardingPrompt.description')}</p>
        <label className="flex flex-col gap-1 text-sm text-text-secondary">
          {t('desktop.onboardingPrompt.timeLabel')}
          <Input
            type="time"
            value={notificationTime ?? ''}
            disabled={notificationTime === null}
            onChange={(e) => setEditedTime(e.target.value)}
          />
        </label>
        <p className="text-xs text-text-faint">{t('desktop.onboardingPrompt.autostartNote')}</p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" disabled={isPending} onClick={() => declineMutation.mutate()}>
            {t('desktop.onboardingPrompt.decline')}
          </Button>
          <Button
            disabled={isPending || !timeIsValid}
            onClick={() => notificationTime && acceptMutation.mutate(notificationTime)}
          >
            {t('desktop.onboardingPrompt.accept')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
